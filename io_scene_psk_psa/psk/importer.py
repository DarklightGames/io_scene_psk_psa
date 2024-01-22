from typing import Optional, List

import bmesh
import bpy
import numpy as np
from bpy.types import VertexGroup
from mathutils import Quaternion, Vector, Matrix

from .data import Psk
from ..helpers import rgb_to_srgb, is_bdk_addon_loaded


class PskImportOptions:
    def __init__(self):
        self.name = ''
        self.should_import_mesh = True
        self.should_reuse_materials = True
        self.should_import_vertex_colors = True
        self.vertex_color_space = 'SRGB'
        self.should_import_vertex_normals = True
        self.should_import_extra_uvs = True
        self.should_import_skeleton = True
        self.should_import_shape_keys = True
        self.bone_length = 1.0
        self.should_import_materials = True


class ImportBone:
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
        self.original_rotation: Quaternion = Quaternion()
        self.original_location: Vector = Vector()
        self.post_rotation: Quaternion = Quaternion()


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

    # MESH
    if options.should_import_mesh:
        mesh_data = bpy.data.meshes.new(options.name)
        mesh_object = bpy.data.objects.new(options.name, mesh_data)

        # MATERIALS
        if options.should_import_materials:
            for material_index, psk_material in enumerate(psk.materials):
                material_name = psk_material.name.decode('utf-8')
                material = None
                if options.should_reuse_materials and material_name in bpy.data.materials:
                    # Material already exists, just re-use it.
                    material = bpy.data.materials[material_name]
                elif is_bdk_addon_loaded() and psk.has_material_references:
                    # Material does not yet exist, and we have the BDK addon installed.
                    # Attempt to load it using BDK addon's operator.
                    material_reference = psk.material_references[material_index]
                    if material_reference and bpy.ops.bdk.link_material(reference=material_reference) == {'FINISHED'}:
                        material = bpy.data.materials[material_name]
                else:
                    # Just create a blank material.
                    material = bpy.data.materials.new(material_name)
                    material.use_nodes = True
                mesh_data.materials.append(material)

        bm = bmesh.new()

        # VERTICES
        for point in psk.points:
            bm.verts.new(tuple(point))

        bm.verts.ensure_lookup_table()

        # FACES
        invalid_face_indices = set()
        for face_index, face in enumerate(psk.faces):
            point_indices = map(lambda i: psk.wedges[i].point_index, reversed(face.wedge_indices))
            points = [bm.verts[i] for i in point_indices]
            try:
                bm_face = bm.faces.new(points)
                bm_face.material_index = face.material_index
            except ValueError:
                # This happens for two reasons:
                # 1. Two or more of the face's points are the same. (i.e, point indices of [0, 0, 1])
                # 2. The face is a duplicate of another face. (i.e., point indices of [0, 1, 2] and [0, 1, 2])
                invalid_face_indices.add(face_index)

        # TODO: Handle invalid faces better.
        if len(invalid_face_indices) > 0:
            result.warnings.append(f'Discarded {len(invalid_face_indices)} invalid face(s).')

        bm.to_mesh(mesh_data)

        # TEXTURE COORDINATES
        data_index = 0
        uv_layer = mesh_data.uv_layers.new(name='VTXW0000')
        for face_index, face in enumerate(psk.faces):
            if face_index in invalid_face_indices:
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
                    if face_index in invalid_face_indices:
                        continue
                    for wedge_index in reversed(face.wedge_indices):
                        u, v = psk.extra_uvs[wedge_index_offset + wedge_index]
                        uv_layer.data[data_index].uv = u, 1.0 - v
                        data_index += 1
                wedge_index_offset += len(psk.wedges)

        # VERTEX COLORS
        if psk.has_vertex_colors and options.should_import_vertex_colors:
            # Convert vertex colors to sRGB if necessary.
            psk_vertex_colors = np.zeros((len(psk.vertex_colors), 4))
            for i in range(len(psk.vertex_colors)):
                psk_vertex_colors[i,:] = psk.vertex_colors[i].normalized()
            match options.vertex_color_space:
                case 'SRGBA':
                    for i in range(psk_vertex_colors.shape[0]):
                        psk_vertex_colors[i, :3] = tuple(map(lambda x: rgb_to_srgb(x), psk_vertex_colors[i, :3]))
                case _:
                    pass

            # Map the PSK vertex colors to the face corners.
            face_corner_colors = np.full((len(psk.faces * 3), 4), 1.0)
            face_corner_color_index = 0
            for face_index, face in enumerate(psk.faces):
                for wedge_index in reversed(face.wedge_indices):
                    face_corner_colors[face_corner_color_index] = psk_vertex_colors[wedge_index]
                    face_corner_color_index += 1

            # Create the vertex color attribute.
            face_corner_color_attribute = mesh_data.attributes.new(name='VERTEXCOLOR', type='FLOAT_COLOR', domain='CORNER')
            face_corner_color_attribute.data.foreach_set('color', face_corner_colors.flatten())

        # VERTEX NORMALS
        if psk.has_vertex_normals and options.should_import_vertex_normals:
            mesh_data.polygons.foreach_set('use_smooth', [True] * len(mesh_data.polygons))
            normals = []
            for vertex_normal in psk.vertex_normals:
                normals.append(tuple(vertex_normal))
            mesh_data.normals_split_custom_set_from_vertices(normals)
            mesh_data.use_auto_smooth = True
        else:
            mesh_data.shade_smooth()

        bm.normal_update()
        bm.free()

        # WEIGHTS
        # Get a list of all bones that have weights associated with them.
        vertex_group_bone_indices = set(map(lambda weight: weight.bone_index, psk.weights))
        vertex_groups: List[Optional[VertexGroup]] = [None] * len(psk.bones)
        for bone_index, psk_bone in map(lambda x: (x, psk.bones[x]), vertex_group_bone_indices):
            vertex_groups[bone_index] = mesh_object.vertex_groups.new(name=psk_bone.name.decode('windows-1252'))

        for weight in psk.weights:
            vertex_groups[weight.bone_index].add((weight.point_index,), weight.weight, 'ADD')

        # MORPHS (SHAPE KEYS)
        if options.should_import_shape_keys:
            morph_data_iterator = iter(psk.morph_data)

            if psk.has_morph_data:
                mesh_object.shape_key_add(name='MORPH_BASE', from_mix=False)

            for morph_info in psk.morph_infos:
                shape_key = mesh_object.shape_key_add(name=morph_info.name.decode('windows-1252'), from_mix=False)

                for _ in range(morph_info.vertex_count):
                    morph_data = next(morph_data_iterator)
                    x, y, z = morph_data.position_delta
                    shape_key.data[morph_data.point_index].co += Vector((x, -y, z))

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
