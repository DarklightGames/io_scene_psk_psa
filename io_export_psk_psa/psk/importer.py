import bpy
import bmesh
import mathutils
from .data import Psk


class PskImporter(object):
    def __init__(self):
        pass

    def import_psk(self, psk: Psk, context):
        # ARMATURE
        armature_data = bpy.data.armatures.new('armature')
        armature_object = bpy.data.objects.new('new_ao', armature_data)
        context.scene.collection.objects.link(armature_object)

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass

        armature_object.select_set(state=True)
        bpy.context.view_layer.objects.active = armature_object

        bpy.ops.object.mode_set(mode='EDIT')

        for bone in psk.bones:
            edit_bone = armature_data.edit_bones.new(bone.name.decode('utf-8'))
            edit_bone.parent = armature_data.edit_bones[bone.parent_index]
            edit_bone.head = (bone.location.x, bone.location.y, bone.location.z)
            rotation = mathutils.Quaternion(*bone.rotation)
            edit_bone.tail = edit_bone.head + (mathutils.Vector(0, 0, 1) @ rotation)

        # MESH
        mesh_data = bpy.data.meshes.new('mesh')
        mesh_object = bpy.data.objects.new('new_mo', mesh_data)

        # MATERIALS
        for material in psk.materials:
            bpy_material = bpy.data.materials.new(material.name.decode('utf-8'))
            mesh_data.materials.append(bpy_material)

        bm = bmesh.new()

        # VERTICES
        for point in psk.points:
            bm.verts.new((point.x, point.y, point.z))

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

        bm.free()

        # TODO: weights (vertex grorups etc.)

        context.scene.collection.objects.link(mesh_object)
