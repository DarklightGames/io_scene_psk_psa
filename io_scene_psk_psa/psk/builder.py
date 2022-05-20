from collections import OrderedDict

from .data import *
from ..helpers import *
import bmesh
import bpy


class PskInputObjects(object):
    def __init__(self):
        self.mesh_objects = []
        self.armature_object = None


class PskBuilderOptions(object):
    def __init__(self):
        self.bone_filter_mode = 'ALL'
        self.bone_group_indices = []
        self.use_raw_mesh_data = True


class PskBuilder(object):
    def __init__(self):
        pass

    @staticmethod
    def get_input_objects(context) -> PskInputObjects:
        input_objects = PskInputObjects()
        for selected_object in context.view_layer.objects.selected:
            if selected_object.type != 'MESH':
                raise RuntimeError(f'Selected object "{selected_object.name}" is not a mesh')

        input_objects.mesh_objects = context.view_layer.objects.selected

        if len(input_objects.mesh_objects) == 0:
            raise RuntimeError('At least one mesh must be selected')

        for mesh_object in input_objects.mesh_objects:
            if len(mesh_object.data.materials) == 0:
                raise RuntimeError(f'Mesh "{mesh_object.name}" must have at least one material')

        # Ensure that there are either no armature modifiers (static mesh)
        # or that there is exactly one armature modifier object shared between
        # all selected meshes
        armature_modifier_objects = set()

        for mesh_object in input_objects.mesh_objects:
            modifiers = [x for x in mesh_object.modifiers if x.type == 'ARMATURE']
            if len(modifiers) == 0:
                continue
            elif len(modifiers) > 1:
                raise RuntimeError(f'Mesh "{mesh_object.name}" must have only one armature modifier')
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
            # If the mesh has no armature object, simply assign it a dummy bone at the root to satisfy the requirement
            # that a PSK file must have at least one bone.
            psk_bone = Psk.Bone()
            psk_bone.name = bytes('root', encoding='windows-1252')
            psk_bone.flags = 0
            psk_bone.children_count = 0
            psk_bone.parent_index = 0
            psk_bone.location = Vector3.zero()
            psk_bone.rotation = Quaternion.identity()
            psk.bones.append(psk_bone)
        else:
            bone_names = get_export_bone_names(armature_object, options.bone_filter_mode, options.bone_group_indices)
            bones = [armature_object.data.bones[bone_name] for bone_name in bone_names]

            for bone in bones:
                psk_bone = Psk.Bone()
                psk_bone.name = bytes(bone.name, encoding='windows-1252')
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

        for input_mesh_object in input_objects.mesh_objects:

            # MATERIALS
            material_indices = []
            for i, material in enumerate(input_mesh_object.data.materials):
                if material is None:
                    raise RuntimeError('Material cannot be empty (index ' + str(i) + ')')
                if material.name in materials:
                    # Material already evaluated, just get its index.
                    material_index = list(materials.keys()).index(material.name)
                else:
                    # New material.
                    psk_material = Psk.Material()
                    psk_material.name = bytes(material.name, encoding='utf-8')
                    psk_material.texture_index = len(psk.materials)
                    psk.materials.append(psk_material)
                    materials[material.name] = material
                    material_index = psk_material.texture_index
                material_indices.append(material_index)

            if options.use_raw_mesh_data:
                mesh_object = input_mesh_object
                mesh_data = input_mesh_object.data
            else:
                # Create a copy of the mesh object after non-armature modifiers are applied.

                # Temporarily deactivate any armature modifiers on the input mesh object.
                active_armature_modifiers = [x for x in filter(lambda x: x.type == 'ARMATURE' and x.is_active, input_mesh_object.modifiers)]
                for modifier in active_armature_modifiers:
                    modifier.show_viewport = False

                depsgraph = context.evaluated_depsgraph_get()
                bm = bmesh.new()
                bm.from_object(input_mesh_object, depsgraph)
                mesh_data = bpy.data.meshes.new('')
                bm.to_mesh(mesh_data)
                del bm
                mesh_object = bpy.data.objects.new('', mesh_data)
                mesh_object.matrix_world = input_mesh_object.matrix_world

                # Copy the vertex groups
                for vertex_group in input_mesh_object.vertex_groups:
                    mesh_object.vertex_groups.new(name=vertex_group.name)

                # Reactivate previously active armature modifiers
                for modifier in active_armature_modifiers:
                    modifier.show_viewport = True

            vertex_offset = len(psk.points)

            # VERTICES
            for vertex in mesh_data.vertices:
                point = Vector3()
                v = mesh_object.matrix_world @ vertex.co
                point.x = v.x
                point.y = v.y
                point.z = v.z
                psk.points.append(point)

            uv_layer = mesh_data.uv_layers.active.data

            # WEDGES
            mesh_data.calc_loop_triangles()

            # Build a list of non-unique wedges.
            wedges = []
            for loop_index, loop in enumerate(mesh_data.loops):
                wedge = Psk.Wedge()
                wedge.point_index = loop.vertex_index + vertex_offset
                wedge.u, wedge.v = uv_layer[loop_index].uv
                wedge.v = 1.0 - wedge.v
                wedges.append(wedge)

            # Assign material indices to the wedges.
            for triangle in mesh_data.loop_triangles:
                for loop_index in triangle.loops:
                    wedges[loop_index].material_index = material_indices[triangle.material_index]

            # Populate the list of wedges with unique wedges & build a look-up table of loop indices to wedge indices
            wedge_indices = {}
            loop_wedge_indices = [-1] * len(mesh_data.loops)
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
            poly_groups, groups = mesh_data.calc_smooth_groups(use_bitflags=True)
            for f in mesh_data.loop_triangles:
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
                vertex_group_names = [x.name for x in mesh_object.vertex_groups]
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
                for vertex_group_index, vertex_group in enumerate(mesh_object.vertex_groups):
                    if vertex_group_index not in vertex_group_bone_indices:
                        # Vertex group has no associated bone, skip it.
                        continue
                    bone_index = vertex_group_bone_indices[vertex_group_index]
                    for vertex_index in range(len(mesh_data.vertices)):
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

            if not options.use_raw_mesh_data:
                bpy.data.objects.remove(mesh_object)
                bpy.data.meshes.remove(mesh_data)
                del mesh_data

        return psk
