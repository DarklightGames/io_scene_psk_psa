from typing import Optional

import bmesh
import bpy
import numpy as np
from bpy.types import Armature, Material

from .data import *
from .properties import triangle_type_and_bit_flags_to_poly_flags
from ..helpers import *


class PskInputObjects(object):
    def __init__(self):
        self.mesh_objects = []
        self.armature_object: Optional[Object] = None


class PskBuildOptions(object):
    def __init__(self):
        self.bone_filter_mode = 'ALL'
        self.bone_collection_indices: List[int] = []
        self.use_raw_mesh_data = True
        self.materials: List[Material] = []
        self.should_enforce_bone_name_restrictions = False


def get_psk_input_objects(context) -> PskInputObjects:
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
        armature_modifier_names = [x.name for x in armature_modifier_objects]
        raise RuntimeError(f'All selected meshes must have the same armature modifier, encountered {len(armature_modifier_names)} ({", ".join(armature_modifier_names)})')
    elif len(armature_modifier_objects) == 1:
        input_objects.armature_object = list(armature_modifier_objects)[0]

    return input_objects


class PskBuildResult(object):
    def __init__(self):
        self.psk = None
        self.warnings: List[str] = []


def build_psk(context, options: PskBuildOptions) -> PskBuildResult:
    input_objects = get_psk_input_objects(context)
    armature_object: bpy.types.Object = input_objects.armature_object

    result = PskBuildResult()
    psk = Psk()
    bones = []

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
        bone_names = get_export_bone_names(armature_object, options.bone_filter_mode, options.bone_collection_indices)
        armature_data = typing.cast(Armature, armature_object.data)
        bones = [armature_data.bones[bone_name] for bone_name in bone_names]

        # Check that all bone names are valid.
        if options.should_enforce_bone_name_restrictions:
            check_bone_names(map(lambda x: x.name, bones))

        for bone in bones:
            psk_bone = Psk.Bone()
            try:
                psk_bone.name = bytes(bone.name, encoding='windows-1252')
            except UnicodeEncodeError:
                raise RuntimeError(
                    f'Bone name "{bone.name}" contains characters that cannot be encoded in the Windows-1252 codepage')
            psk_bone.flags = 0
            psk_bone.children_count = 0

            try:
                parent_index = bones.index(bone.parent)
                psk_bone.parent_index = parent_index
                psk.bones[parent_index].children_count += 1
            except ValueError:
                psk_bone.parent_index = 0

            if bone.parent is not None:
                rotation = bone.matrix.to_quaternion().conjugated()
                inverse_parent_rotation = bone.parent.matrix.to_quaternion().inverted()
                parent_head = inverse_parent_rotation @ bone.parent.head
                parent_tail = inverse_parent_rotation @ bone.parent.tail
                location = (parent_tail - parent_head) + bone.head
            else:
                armature_local_matrix = armature_object.matrix_local
                location = armature_local_matrix @ bone.head
                bone_rotation = bone.matrix.to_quaternion().conjugated()
                local_rotation = armature_local_matrix.to_3x3().to_quaternion().conjugated()
                rotation = bone_rotation @ local_rotation
                rotation.conjugate()

            psk_bone.location.x = location.x
            psk_bone.location.y = location.y
            psk_bone.location.z = location.z

            psk_bone.rotation.w = rotation.w
            psk_bone.rotation.x = rotation.x
            psk_bone.rotation.y = rotation.y
            psk_bone.rotation.z = rotation.z

            psk.bones.append(psk_bone)

    # MATERIALS
    for material in options.materials:
        psk_material = Psk.Material()
        try:
            psk_material.name = bytes(material.name, encoding='windows-1252')
        except UnicodeEncodeError:
            raise RuntimeError(f'Material name "{material.name}" contains characters that cannot be encoded in the Windows-1252 codepage')
        psk_material.texture_index = len(psk.materials)
        psk_material.poly_flags = triangle_type_and_bit_flags_to_poly_flags(material.psk.mesh_triangle_type,
                                                                            material.psk.mesh_triangle_bit_flags)
        psk.materials.append(psk_material)

    context.window_manager.progress_begin(0, len(input_objects.mesh_objects))

    material_names = [m.name for m in options.materials]

    for object_index, input_mesh_object in enumerate(input_objects.mesh_objects):

        should_flip_normals = False

        # MATERIALS
        material_indices = [material_names.index(material_slot.material.name) for material_slot in input_mesh_object.material_slots]

        # MESH DATA
        if options.use_raw_mesh_data:
            mesh_object = input_mesh_object
            mesh_data = input_mesh_object.data
        else:
            # Create a copy of the mesh object after non-armature modifiers are applied.

            # Temporarily force the armature into the rest position.
            # We will undo this later.
            old_pose_position = None
            if armature_object is not None:
                old_pose_position = armature_object.data.pose_position
                armature_object.data.pose_position = 'REST'

            depsgraph = context.evaluated_depsgraph_get()
            bm = bmesh.new()
            bm.from_object(input_mesh_object, depsgraph)
            mesh_data = bpy.data.meshes.new('')
            bm.to_mesh(mesh_data)
            del bm
            mesh_object = bpy.data.objects.new('', mesh_data)
            mesh_object.matrix_world = input_mesh_object.matrix_world

            scale = (input_mesh_object.scale.x, input_mesh_object.scale.y, input_mesh_object.scale.z)

            # Negative scaling in Blender results in inverted normals after the scale is applied. However, if the scale
            # is not applied, the normals will appear unaffected in the viewport. The evaluated mesh data used in the
            # export will have the scale applied, but this behavior is not obvious to the user.
            #
            # In order to have the exporter be as WYSIWYG as possible, we need to check for negative scaling and invert
            # the normals if necessary. If two axes have negative scaling and the third has positive scaling, the
            # normals will be correct. We can detect this by checking if the number of negative scaling axes is odd. If
            # it is, we need to invert the normals of the mesh by swapping the order of the vertices in each face.
            should_flip_normals = sum(1 for x in scale if x < 0) % 2 == 1

            # Copy the vertex groups
            for vertex_group in input_mesh_object.vertex_groups:
                mesh_object.vertex_groups.new(name=vertex_group.name)

            # Restore the previous pose position on the armature.
            if old_pose_position is not None:
                armature_object.data.pose_position = old_pose_position

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
            wedges.append(Psk.Wedge(
                point_index=loop.vertex_index + vertex_offset,
                u=uv_layer[loop_index].uv[0],
                v=1.0 - uv_layer[loop_index].uv[1]
            ))

        # Assign material indices to the wedges.
        for triangle in mesh_data.loop_triangles:
            for loop_index in triangle.loops:
                wedges[loop_index].material_index = material_indices[triangle.material_index]

        # Populate the list of wedges with unique wedges & build a look-up table of loop indices to wedge indices
        wedge_indices = dict()
        loop_wedge_indices = np.full(len(mesh_data.loops), -1)
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
        psk_face_start_index = len(psk.faces)
        for f in mesh_data.loop_triangles:
            face = Psk.Face()
            face.material_index = material_indices[f.material_index]
            face.wedge_indices[0] = loop_wedge_indices[f.loops[2]]
            face.wedge_indices[1] = loop_wedge_indices[f.loops[1]]
            face.wedge_indices[2] = loop_wedge_indices[f.loops[0]]
            face.smoothing_groups = poly_groups[f.polygon_index]
            psk.faces.append(face)

        if should_flip_normals:
            # Invert the normals of the faces.
            for face in psk.faces[psk_face_start_index:]:
                face.wedge_indices[0], face.wedge_indices[2] = face.wedge_indices[2], face.wedge_indices[0]

        # WEIGHTS
        if armature_object is not None:
            armature_data = typing.cast(Armature, armature_object.data)
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
                    if vertex_group_name in armature_data.bones:
                        bone = armature_data.bones[vertex_group_name]
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

        context.window_manager.progress_update(object_index)

    context.window_manager.progress_end()

    result.psk = psk

    return result
