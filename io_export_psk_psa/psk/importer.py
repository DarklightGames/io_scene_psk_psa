import os
import bpy
import bmesh
from typing import Optional
from .data import Psk
from mathutils import Quaternion, Vector, Matrix
from .reader import PskReader
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper


class PskImporter(object):
    def __init__(self):
        pass

    def import_psk(self, psk: Psk, name: str, context):
        # ARMATURE
        armature_data = bpy.data.armatures.new(name)
        armature_object = bpy.data.objects.new(name, armature_data)
        armature_object.show_in_front = True

        context.scene.collection.objects.link(armature_object)

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass

        armature_object.select_set(state=True)
        bpy.context.view_layer.objects.active = armature_object

        bpy.ops.object.mode_set(mode='EDIT')

        # Intermediate bone type for the purpose of construction.
        class ImportBone(object):
            def __init__(self, index: int, psk_bone: Psk.Bone):
                self.index: int = index
                self.psk_bone: Psk.Bone = psk_bone
                self.parent: Optional[ImportBone] = None
                self.local_rotation: Quaternion = Quaternion()
                self.local_translation: Vector = Vector()
                self.world_rotation_matrix: Matrix = Matrix()
                self.world_matrix: Matrix = Matrix()
                self.vertex_group = None

        import_bones = []
        should_invert_root = False
        new_bone_size = 8.0

        for bone_index, psk_bone in enumerate(psk.bones):
            import_bone = ImportBone(bone_index, psk_bone)
            psk_bone.parent_index = max(0, psk_bone.parent_index)
            import_bone.local_rotation = Quaternion(tuple(psk_bone.rotation))
            import_bone.local_translation = Vector(tuple(psk_bone.location))
            if psk_bone.parent_index == 0 and bone_index == 0:
                if should_invert_root:
                    import_bone.world_rotation_matrix = import_bone.local_rotation.conjugated().to_matrix()
                else:
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

        for bone in import_bones:
            edit_bone = armature_data.edit_bones.new(bone.psk_bone.name.decode('utf-8'))
            if bone.parent is not None:
                edit_bone.parent = armature_data.edit_bones[bone.psk_bone.parent_index]
            elif not should_invert_root:
                bone.local_rotation.conjugate()
            post_quat = bone.local_rotation.conjugated()
            edit_bone.tail = Vector((0.0, new_bone_size, 0.0))
            m = post_quat.copy()
            m.rotate(bone.world_matrix)
            m = m.to_matrix().to_4x4()
            m.translation = bone.world_matrix.translation
            edit_bone.matrix = m

        # MESH
        mesh_data = bpy.data.meshes.new(name)
        mesh_object = bpy.data.objects.new(name, mesh_data)

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

        for face in psk.faces:
            point_indices = [bm.verts[psk.wedges[i].point_index] for i in reversed(face.wedge_indices)]
            bm_face = bm.faces.new(point_indices)
            bm_face.material_index = face.material_index

        bm.to_mesh(mesh_data)

        # TEXTURE COORDINATES
        data_index = 0
        uv_layer = mesh_data.uv_layers.new()
        for face_index, face in enumerate(psk.faces):
            face_wedges = [psk.wedges[i] for i in reversed(face.wedge_indices)]
            for wedge in face_wedges:
                uv_layer.data[data_index].uv = wedge.u, 1.0 - wedge.v
                data_index += 1

        bm.normal_update()
        bm.free()

        # VERTEX WEIGHTS

        # Get a list of all bones that have weights associated with them.
        vertex_group_bone_indices = set(map(lambda weight: weight.bone_index, psk.weights))
        for bone_index in sorted(list(vertex_group_bone_indices)):
            import_bones[bone_index].vertex_group = mesh_object.vertex_groups.new(name=import_bones[bone_index].psk_bone.name.decode('windows-1252'))

        for weight in psk.weights:
            import_bones[weight.bone_index].vertex_group.add((weight.point_index,), weight.weight, 'ADD')

        # Add armature modifier to our mesh object.
        armature_modifier = mesh_object.modifiers.new(name='Armature', type='ARMATURE')
        armature_modifier.object = armature_object
        mesh_object.parent = armature_object

        context.scene.collection.objects.link(mesh_object)

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass


class PskImportOperator(Operator, ImportHelper):
    bl_idname = 'import.psk'
    bl_label = 'Export'
    __doc__ = 'PSK Importer (.psk)'
    filename_ext = '.psk'
    filter_glob: StringProperty(default='*.psk', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='')

    def execute(self, context):
        reader = PskReader()
        psk = reader.read(self.filepath)
        name = os.path.splitext(os.path.basename(self.filepath))[0]
        PskImporter().import_psk(psk, name, context)
        return {'FINISHED'}