import bpy
import bmesh
from collections import OrderedDict
from .data import *

# https://github.com/bwrsandman/blender-addons/blob/master/io_export_unreal_psk_psa.py

class PskInputObjects(object):
    def __init__(self):
        self.mesh_objects = []
        self.armature_object = None

class PskBuilder(object):
    def __init__(self):
        pass

    @staticmethod
    def get_input_objects(context) -> PskInputObjects:
        input_objects = PskInputObjects()
        for obj in context.view_layer.objects.selected:
            if obj.type != 'MESH':
                raise RuntimeError(f'Selected object "{obj.name}" is not a mesh')

        input_objects.mesh_objects = context.view_layer.objects.selected

        if len(input_objects.mesh_objects) == 0:
            raise RuntimeError('At least one mesh must be selected')

        for obj in input_objects.mesh_objects:
            if len(obj.data.materials) == 0:
                raise RuntimeError(f'Mesh "{obj.name}" must have at least one material')

        # Ensure that there are either no armature modifiers (static mesh)
        # or that there is exactly one armature modifier object shared between
        # all selected meshes
        armature_modifier_objects = set()

        for obj in input_objects.mesh_objects:
            modifiers = [x for x in obj.modifiers if x.type == 'ARMATURE']
            if len(modifiers) == 0:
                continue
            elif len(modifiers) == 2:
                raise RuntimeError(f'Mesh "{obj.name}" must have only one armature modifier')
            armature_modifier_objects.add(modifiers[0].object)

        if len(armature_modifier_objects) > 1:
            raise RuntimeError('All selected meshes must have the same armature modifier')
        elif len(armature_modifier_objects) == 1:
            input_objects.armature_object = list(armature_modifier_objects)[0]

        return input_objects

    def build(self, context) -> Psk:
        input_objects = PskBuilder.get_input_objects(context)
        wedge_count = sum([len(m.data.loops) for m in input_objects.mesh_objects])
        if wedge_count <= 65536:
            wedge_type = Psk.Wedge16
        else:
            wedge_type = Psk.Wedge32

        psk = Psk()

        materials = OrderedDict()

        if input_objects.armature_object is None:
            # Static mesh (no armature)
            psk_bone = Psk.Bone()
            psk_bone.name = bytes('static', encoding='utf-8')
            psk_bone.flags = 0
            psk_bone.children_count = 0
            psk_bone.parent_index = 0
            psk_bone.location = Vector3(0, 0, 0)
            psk_bone.rotation = Quaternion(0, 0, 0, 1)
            psk.bones.append(psk_bone)
        else:
            bones = list(input_objects.armature_object.data.bones)
            for bone in bones:
                psk_bone = Psk.Bone()
                psk_bone.name = bytes(bone.name, encoding='utf-8')
                psk_bone.flags = 0
                psk_bone.children_count = len(bone.children)

                try:
                    psk_bone.parent_index = bones.index(bone.parent)
                except ValueError:
                    psk_bone.parent_index = 0

                if bone.parent is not None:
                    rotation = bone.matrix.to_quaternion()
                    rotation.x = -rotation.x
                    rotation.y = -rotation.y
                    rotation.z = -rotation.z
                    quat_parent = bone.parent.matrix.to_quaternion().inverted()
                    parent_head = quat_parent @ bone.parent.head
                    parent_tail = quat_parent @ bone.parent.tail
                    location = (parent_tail - parent_head) + bone.head
                else:
                    location = input_objects.armature_object.matrix_local @ bone.head
                    rot_matrix = bone.matrix @ input_objects.armature_object.matrix_local.to_3x3()
                    rotation = rot_matrix.to_quaternion()

                psk_bone.location.x = location.x
                psk_bone.location.y = location.y
                psk_bone.location.z = location.z

                psk_bone.rotation.x = rotation.x
                psk_bone.rotation.y = rotation.y
                psk_bone.rotation.z = rotation.z
                psk_bone.rotation.w = rotation.w

                psk.bones.append(psk_bone)

        vertex_offset = 0
        wedge_offset = 0
        weight_offset = 0

        # TODO: if there is an edge-split modifier, we need to apply it (maybe?)
        for object in input_objects.mesh_objects:
            # VERTICES
            for vertex in object.data.vertices:
                point = Vector3()
                v = object.matrix_world @ vertex.co
                point.x = v.x
                point.y = v.y
                point.z = v.z
                psk.points.append(point)

            # WEDGES
            uv_layer = object.data.uv_layers.active.data
            psk.wedges.extend([wedge_type() for _ in range(len(object.data.loops))])

            for loop_index, loop in enumerate(object.data.loops):
                wedge = psk.wedges[wedge_offset + loop_index]
                wedge.material_index = 0  # NOTE: this material index is set properly while building the faces
                wedge.point_index = loop.vertex_index + vertex_offset
                wedge.u, wedge.v = uv_layer[loop_index].uv
                wedge.v = 1.0 - wedge.v
                psk.wedges.append(wedge)

            # MATERIALS
            material_indices = []
            for i, m in enumerate(object.data.materials):
                if m is None:
                    raise RuntimeError('Material cannot be empty (index ' + str(i) + ')')
                if m.name in materials:
                    material_index = list(materials.keys()).index(m.name)
                else:
                    material = Psk.Material()
                    material.name = bytes(m.name, encoding='utf-8')
                    material.texture_index = len(psk.materials)
                    psk.materials.append(material)
                    materials[m.name] = m
                    material_index = material.texture_index
                material_indices.append(material_index)

            # FACES
            object.data.calc_loop_triangles()
            poly_groups, groups = object.data.calc_smooth_groups(use_bitflags=True)
            for f in object.data.loop_triangles:
                face = Psk.Face()
                face.material_index = material_indices[f.material_index]
                face.wedge_index_1 = f.loops[2] + wedge_offset
                face.wedge_index_2 = f.loops[1] + wedge_offset
                face.wedge_index_3 = f.loops[0] + wedge_offset
                face.smoothing_groups = poly_groups[f.polygon_index]
                psk.faces.append(face)
                # update the material index of the wedges
                for i in range(3):
                    psk.wedges[wedge_offset + f.loops[i]].material_index = face.material_index

            # WEIGHTS
            # TODO: bone ~> vg might not be 1:1, provide a nice error message if this is the case
            if input_objects.armature_object is not None:
                armature = input_objects.armature_object.data
                bone_names = [x.name for x in armature.bones]
                vertex_group_names = [x.name for x in object.vertex_groups]
                bone_indices = [bone_names.index(name) for name in vertex_group_names]
                for vertex_group_index, vertex_group in enumerate(object.vertex_groups):
                    bone_index = bone_indices[vertex_group_index]
                    for vertex_index in range(len(object.data.vertices)):
                        try:
                            weight = vertex_group.weight(vertex_index)
                        except RuntimeError:
                            continue
                        if weight == 0.0:
                            continue
                        w = Psk.Weight()
                        w.bone_index = bone_index
                        w.point_index = vertex_offset + vertex_index
                        w.weight = weight
                        psk.weights.append(w)

            vertex_offset += len(psk.points)
            wedge_offset += len(psk.wedges)
            weight_offset += len(psk.weights)

        return psk
