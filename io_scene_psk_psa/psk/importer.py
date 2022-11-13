import os
import sys
from math import inf
from typing import Optional, List

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy.types import Operator, PropertyGroup, VertexGroup
from bpy_extras.io_utils import ImportHelper
from mathutils import Quaternion, Vector, Matrix

from .data import Psk
from .reader import read_psk
from ..helpers import rgb_to_srgb


class PskImportOptions(object):
    def __init__(self):
        self.name = ''
        self.should_import_mesh = True
        self.should_import_vertex_colors = True
        self.vertex_color_space = 'sRGB'
        self.should_import_vertex_normals = True
        self.should_import_extra_uvs = True
        self.should_import_skeleton = True
        self.bone_length = 1.0


class ImportBone(object):
    """
    Intermediate bone type for the purpose of construction.
    """
    def __init__(self, index: int, psk_bone: Psk.Bone):
        self.index: int = index
        self.psk_bone: Psk.Bone = psk_bone
        self.parent: Optional[ImportBone] = None
        self.local_rotation: Quaternion = Quaternion()
        self.local_translation: Vector = Vector()
        self.world_rotation_matrix: Matrix = Matrix()
        self.world_matrix: Matrix = Matrix()
        self.vertex_group = None
        self.orig_quat: Quaternion = Quaternion()
        self.orig_loc: Vector = Vector()
        self.post_quat: Quaternion = Quaternion()


class PskImportResult:
    def __init__(self):
        self.warnings: List[str] = []


def import_psk(psk: Psk, context, options: PskImportOptions) -> PskImportResult:
    result = PskImportResult()
    armature_object = None

    if options.should_import_skeleton:
        # ARMATURE
        armature_data = bpy.data.armatures.new(options.name)
        armature_object = bpy.data.objects.new(options.name, armature_data)
        armature_object.show_in_front = True

        context.scene.collection.objects.link(armature_object)

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass

        armature_object.select_set(state=True)
        bpy.context.view_layer.objects.active = armature_object

        bpy.ops.object.mode_set(mode='EDIT')

        import_bones = []

        for bone_index, psk_bone in enumerate(psk.bones):
            import_bone = ImportBone(bone_index, psk_bone)
            psk_bone.parent_index = max(0, psk_bone.parent_index)
            import_bone.local_rotation = Quaternion(tuple(psk_bone.rotation))
            import_bone.local_translation = Vector(tuple(psk_bone.location))
            if psk_bone.parent_index == 0 and bone_index == 0:
                import_bone.world_rotation_matrix = import_bone.local_rotation.to_matrix()
                import_bone.world_matrix = Matrix.Translation(import_bone.local_translation)
            import_bones.append(import_bone)

        for bone_index, bone in enumerate(import_bones):
            if bone.psk_bone.parent_index == 0 and bone_index == 0:
                continue
            parent = import_bones[bone.psk_bone.parent_index]
            bone.parent = parent
            bone.world_matrix = parent.world_rotation_matrix.to_4x4()
            translation = bone.local_translation.copy()
            translation.rotate(parent.world_rotation_matrix)
            bone.world_matrix.translation = parent.world_matrix.translation + translation
            bone.world_rotation_matrix = bone.local_rotation.conjugated().to_matrix()
            bone.world_rotation_matrix.rotate(parent.world_rotation_matrix)

        for import_bone in import_bones:
            bone_name = import_bone.psk_bone.name.decode('utf-8')
            edit_bone = armature_data.edit_bones.new(bone_name)

            if import_bone.parent is not None:
                edit_bone.parent = armature_data.edit_bones[import_bone.psk_bone.parent_index]
            else:
                import_bone.local_rotation.conjugate()

            edit_bone.tail = Vector((0.0, options.bone_length, 0.0))
            edit_bone_matrix = import_bone.local_rotation.conjugated()
            edit_bone_matrix.rotate(import_bone.world_matrix)
            edit_bone_matrix = edit_bone_matrix.to_matrix().to_4x4()
            edit_bone_matrix.translation = import_bone.world_matrix.translation
            edit_bone.matrix = edit_bone_matrix

            # Store bind pose information in the bone's custom properties.
            # This information is used when importing animations from PSA files.
            edit_bone['orig_quat'] = import_bone.local_rotation
            edit_bone['orig_loc'] = import_bone.local_translation
            edit_bone['post_quat'] = import_bone.local_rotation.conjugated()

    # MESH
    if options.should_import_mesh:
        mesh_data = bpy.data.meshes.new(options.name)
        mesh_object = bpy.data.objects.new(options.name, mesh_data)

        # MATERIALS
        for material in psk.materials:
            # TODO: re-use of materials should be an option
            bpy_material = bpy.data.materials.new(material.name.decode('utf-8'))
            mesh_data.materials.append(bpy_material)

        bm = bmesh.new()

        # VERTICES
        for point in psk.points:
            bm.verts.new(tuple(point))

        bm.verts.ensure_lookup_table()

        degenerate_face_indices = set()
        for face_index, face in enumerate(psk.faces):
            point_indices = [bm.verts[psk.wedges[i].point_index] for i in reversed(face.wedge_indices)]
            try:
                bm_face = bm.faces.new(point_indices)
                bm_face.material_index = face.material_index
            except ValueError:
                degenerate_face_indices.add(face_index)

        if len(degenerate_face_indices) > 0:
            result.warnings.append(f'Discarded {len(degenerate_face_indices)} degenerate face(s).')

        bm.to_mesh(mesh_data)

        # TEXTURE COORDINATES
        data_index = 0
        uv_layer = mesh_data.uv_layers.new(name='VTXW0000')
        for face_index, face in enumerate(psk.faces):
            if face_index in degenerate_face_indices:
                continue
            face_wedges = [psk.wedges[i] for i in reversed(face.wedge_indices)]
            for wedge in face_wedges:
                uv_layer.data[data_index].uv = wedge.u, 1.0 - wedge.v
                data_index += 1

        # EXTRA UVS
        if psk.has_extra_uvs and options.should_import_extra_uvs:
            extra_uv_channel_count = int(len(psk.extra_uvs) / len(psk.wedges))
            wedge_index_offset = 0
            for extra_uv_index in range(extra_uv_channel_count):
                data_index = 0
                uv_layer = mesh_data.uv_layers.new(name=f'EXTRAUV{extra_uv_index}')
                for face_index, face in enumerate(psk.faces):
                    if face_index in degenerate_face_indices:
                        continue
                    for wedge_index in reversed(face.wedge_indices):
                        u, v = psk.extra_uvs[wedge_index_offset + wedge_index]
                        uv_layer.data[data_index].uv = u, 1.0 - v
                        data_index += 1
                wedge_index_offset += len(psk.wedges)

        # VERTEX COLORS
        if psk.has_vertex_colors and options.should_import_vertex_colors:
            size = (len(psk.points), 4)
            vertex_colors = np.full(size, inf)
            vertex_color_data = mesh_data.vertex_colors.new(name='VERTEXCOLOR')
            ambiguous_vertex_color_point_indices = []

            for wedge_index, wedge in enumerate(psk.wedges):
                point_index = wedge.point_index
                psk_vertex_color = psk.vertex_colors[wedge_index].normalized()
                if vertex_colors[point_index, 0] != inf and tuple(vertex_colors[point_index]) != psk_vertex_color:
                    ambiguous_vertex_color_point_indices.append(point_index)
                else:
                    vertex_colors[point_index] = psk_vertex_color

            if options.vertex_color_space == 'SRGBA':
                for i in range(vertex_colors.shape[0]):
                    vertex_colors[i, :3] = tuple(map(lambda x: rgb_to_srgb(x), vertex_colors[i, :3]))

            for loop_index, loop in enumerate(mesh_data.loops):
                vertex_color = vertex_colors[loop.vertex_index]
                if vertex_color is not None:
                    vertex_color_data.data[loop_index].color = vertex_color
                else:
                    vertex_color_data.data[loop_index].color = 1.0, 1.0, 1.0, 1.0

            if len(ambiguous_vertex_color_point_indices) > 0:
                result.warnings.append(
                    f'{len(ambiguous_vertex_color_point_indices)} vertex(es) with ambiguous vertex colors.')

        # VERTEX NORMALS
        if psk.has_vertex_normals and options.should_import_vertex_normals:
            mesh_data.polygons.foreach_set("use_smooth", [True] * len(mesh_data.polygons))
            normals = []
            for vertex_normal in psk.vertex_normals:
                normals.append(tuple(vertex_normal))
            mesh_data.normals_split_custom_set_from_vertices(normals)
            mesh_data.use_auto_smooth = True

        bm.normal_update()
        bm.free()

        # Get a list of all bones that have weights associated with them.
        vertex_group_bone_indices = set(map(lambda weight: weight.bone_index, psk.weights))
        vertex_groups: List[Optional[VertexGroup]] = [None] * len(psk.bones)
        for bone_index, psk_bone in map(lambda x: (x, psk.bones[x]), vertex_group_bone_indices):
            vertex_groups[bone_index] = mesh_object.vertex_groups.new(name=psk_bone.name.decode('windows-1252'))

        for weight in psk.weights:
            vertex_groups[weight.bone_index].add((weight.point_index,), weight.weight, 'ADD')

        context.scene.collection.objects.link(mesh_object)

        # Add armature modifier to our mesh object.
        if options.should_import_skeleton:
            armature_modifier = mesh_object.modifiers.new(name='Armature', type='ARMATURE')
            armature_modifier.object = armature_object
            mesh_object.parent = armature_object

    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except:
        pass

    return result


empty_set = set()


class PskImportPropertyGroup(PropertyGroup):
    should_import_vertex_colors: BoolProperty(
        default=True,
        options=empty_set,
        name='Vertex Colors',
        description='Import vertex colors from PSKX files, if available'
    )
    vertex_color_space: EnumProperty(
        name='Vertex Color Space',
        options=empty_set,
        description='The source vertex color space',
        default='SRGBA',
        items=(
            ('LINEAR', 'Linear', ''),
            ('SRGBA', 'sRGBA', ''),
        )
    )
    should_import_vertex_normals: BoolProperty(
        default=True,
        name='Vertex Normals',
        options=empty_set,
        description='Import vertex normals from PSKX files, if available'
    )
    should_import_extra_uvs: BoolProperty(
        default=True,
        name='Extra UVs',
        options=empty_set,
        description='Import extra UV maps from PSKX files, if available'
    )
    should_import_mesh: BoolProperty(
        default=True,
        name='Import Mesh',
        options=empty_set,
        description='Import mesh'
    )
    should_import_skeleton: BoolProperty(
        default=True,
        name='Import Skeleton',
        options=empty_set,
        description='Import skeleton'
    )
    bone_length: FloatProperty(
        default=1.0,
        min=sys.float_info.epsilon,
        step=100,
        soft_min=1.0,
        name='Bone Length',
        options=empty_set,
        description='Length of the bones'
    )


class PskImportOperator(Operator, ImportHelper):
    bl_idname = 'import.psk'
    bl_label = 'Import'
    bl_options = {'INTERNAL', 'UNDO'}
    __doc__ = 'Load a PSK file'
    filename_ext = '.psk'
    filter_glob: StringProperty(default='*.psk;*.pskx', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='')

    def execute(self, context):
        pg = getattr(context.scene, 'psk_import')

        psk = read_psk(self.filepath)

        options = PskImportOptions()
        options.name = os.path.splitext(os.path.basename(self.filepath))[0]
        options.should_import_mesh = pg.should_import_mesh
        options.should_import_extra_uvs = pg.should_import_extra_uvs
        options.should_import_vertex_colors = pg.should_import_vertex_colors
        options.should_import_vertex_normals = pg.should_import_vertex_normals
        options.vertex_color_space = pg.vertex_color_space
        options.should_import_skeleton = pg.should_import_skeleton
        options.bone_length = pg.bone_length

        result = import_psk(psk, context, options)

        if len(result.warnings):
            message = f'PSK imported with {len(result.warnings)} warning(s)\n'
            message += '\n'.join(result.warnings)
            self.report({'WARNING'}, message)
        else:
            self.report({'INFO'}, f'PSK imported')

        return {'FINISHED'}

    def draw(self, context):
        pg = getattr(context.scene, 'psk_import')
        layout = self.layout
        layout.prop(pg, 'should_import_mesh')
        row = layout.column()
        row.use_property_split = True
        row.use_property_decorate = False
        if pg.should_import_mesh:
            row.prop(pg, 'should_import_vertex_normals')
            row.prop(pg, 'should_import_extra_uvs')
            row.prop(pg, 'should_import_vertex_colors')
            if pg.should_import_vertex_colors:
                row.prop(pg, 'vertex_color_space')
        layout.prop(pg, 'should_import_skeleton')
        row = layout.column()
        row.use_property_split = True
        row.use_property_decorate = False
        if pg.should_import_skeleton:
            row.prop(pg, 'bone_length')


classes = (
    PskImportOperator,
    PskImportPropertyGroup,
)
