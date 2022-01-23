import bpy
import bmesh
from collections import OrderedDict
from .data import *
from ..helpers import *


class PskInputObjects(object):
    def __init__(self):
        self.mesh_objects = []
        self.armature_object = None


class PskBuilderOptions(object):
    def __init__(self):
        self.bone_filter_mode = 'ALL'
        self.bone_group_indices = []


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
            elif len(modifiers) > 1:
                raise RuntimeError(f'Mesh "{obj.name}" must have only one armature modifier')
            armature_modifier_objects.add(modifiers[0].object)

        if len(armature_modifier_objects) > 1:
            raise RuntimeError('All selected meshes must have the same armature modifier')
        elif len(armature_modifier_objects) == 1:
            input_objects.armature_object = list(armature_modifier_objects)[0]

        return input_objects

    def build(self, context, options: PskBuilderOptions) -> Psk:
        input_objects = PskBuilder.get_input_objects(context)

        armature_object = input_objects.armature_object

        psk = Psk()
        bones = []
        materials = OrderedDict()

        if armature_object is None:
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
            bones = list(armature_object.data.bones)

            # If bone groups are specified, get only the bones that are in the specified bone groups and their ancestors.
            if len(options.bone_group_indices) > 0:
                bone_indices = get_export_bone_indices_for_bone_groups(armature_object, options.bone_group_indices)
                bones = [bones[bone_index] for bone_index in bone_indices]

            # Ensure that the exported hierarchy has a single root bone.
            root_bones = [x for x in bones if x.parent is None]
            if len(root_bones) > 1:
                root_bone_names = [x.name for x in bones]
                raise RuntimeError('Exported bone hierarchy must have a single root bone.'
                                   f'The bone hierarchy marked for export has {len(root_bones)} root bones: {root_bone_names}')

            for bone in bones:
                psk_bone = Psk.Bone()
                psk_bone.name = bytes(bone.name, encoding='utf-8')
                psk_bone.flags = 0
                psk_bone.children_count = 0

                try:
                    parent_index = bones.index(bone.parent)
                    psk_bone.parent_index = parent_index
                    psk.bones[parent_index].children_count += 1
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
                    location = armature_object.matrix_local @ bone.head
                    rot_matrix = bone.matrix @ armature_object.matrix_local.to_3x3()
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

        for object in input_objects.mesh_objects:
            # VERTICES
            for vertex in object.data.vertices:
                point = Vector3()
                v = object.matrix_world @ vertex.co
                point.x = v.x
                point.y = v.y
                point.z = v.z
                psk.points.append(point)

            uv_layer = object.data.uv_layers.active.data

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

            # WEDGES
            object.data.calc_loop_triangles()

            # Build a list of non-unique wedges.
            wedges = []
            for loop_index, loop in enumerate(object.data.loops):
                wedge = Psk.Wedge()
                wedge.point_index = loop.vertex_index + vertex_offset
                wedge.u, wedge.v = uv_layer[loop_index].uv
                wedge.v = 1.0 - wedge.v
                wedges.append(wedge)

            # Assign material indices to the wedges.
            for triangle in object.data.loop_triangles:
                for loop_index in triangle.loops:
                    wedges[loop_index].material_index = material_indices[triangle.material_index]

            # Populate the list of wedges with unique wedges & build a look-up table of loop indices to wedge indices
            wedge_indices = {}
            loop_wedge_indices = [-1] * len(object.data.loops)
            for loop_index, wedge in enumerate(wedges):
                wedge_hash = hash(wedge)
                if wedge_hash in wedge_indices:
                    loop_wedge_indices[loop_index] = wedge_indices[wedge_hash]
                else:
                    wedge_index = len(psk.wedges)
                    wedge_indices[wedge_hash] = wedge_index
                    psk.wedges.append(wedge)
                    loop_wedge_indices[loop_index] = wedge_index

            # FACES
            poly_groups, groups = object.data.calc_smooth_groups(use_bitflags=True)
            for f in object.data.loop_triangles:
                face = Psk.Face()
                face.material_index = material_indices[f.material_index]
                face.wedge_indices[0] = loop_wedge_indices[f.loops[2]]
                face.wedge_indices[1] = loop_wedge_indices[f.loops[1]]
                face.wedge_indices[2] = loop_wedge_indices[f.loops[0]]
                face.smoothing_groups = poly_groups[f.polygon_index]
                psk.faces.append(face)

            # WEIGHTS
            if armature_object is not None:
                # Because the vertex groups may contain entries for which there is no matching bone in the armature,
                # we must filter them out and not export any weights for these vertex groups.
                bone_names = [x.name for x in bones]
                vertex_group_names = [x.name for x in object.vertex_groups]
                vertex_group_bone_indices = dict()
                for vertex_group_index, vertex_group_name in enumerate(vertex_group_names):
                    try:
                        vertex_group_bone_indices[vertex_group_index] = bone_names.index(vertex_group_name)
                    except ValueError:
                        # The vertex group does not have a matching bone in the list of bones to be exported.
                        # Check to see if there is an associated bone for this vertex group that exists in the armature.
                        # If there is, we can traverse the ancestors of that bone to find an alternate bone to use for
                        # weighting the vertices belonging to this vertex group.
                        if vertex_group_name in armature_object.data.bones:
                            bone = armature_object.data.bones[vertex_group_name]
                            while bone is not None:
                                try:
                                    bone_index = bone_names.index(bone.name)
                                    vertex_group_bone_indices[vertex_group_index] = bone_index
                                    break
                                except ValueError:
                                    bone = bone.parent
                for vertex_group_index, vertex_group in enumerate(object.vertex_groups):
                    if vertex_group_index not in vertex_group_bone_indices:
                        continue
                    bone_index = vertex_group_bone_indices[vertex_group_index]
                    # TODO: exclude vertex group if it doesn't match to a bone we are exporting
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

            vertex_offset = len(psk.points)

        return psk
