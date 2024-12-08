import typing
from typing import Optional

import bmesh
import numpy as np
from bpy.types import Material, Collection, Context
from mathutils import Matrix, Vector

from .data import *
from .properties import triangle_type_and_bit_flags_to_poly_flags
from ..shared.dfs import dfs_collection_objects, dfs_view_layer_objects, DfsObject
from ..shared.helpers import *


class PskInputObjects(object):
    def __init__(self):
        self.mesh_objects: List[DfsObject] = []
        self.armature_object: Optional[Object] = None


class PskBuildOptions(object):
    def __init__(self):
        self.bone_filter_mode = 'ALL'
        self.bone_collection_indices: List[int] = []
        self.object_eval_state = 'EVALUATED'
        self.materials: List[Material] = []
        self.scale = 1.0
        self.export_space = 'WORLD'
        self.forward_axis = 'X'
        self.up_axis = 'Z'


def get_vector_from_axis_identifier(axis_identifier: str) -> Vector:
    match axis_identifier:
        case 'X':
            return Vector((1.0, 0.0, 0.0))
        case 'Y':
            return Vector((0.0, 1.0, 0.0))
        case 'Z':
            return Vector((0.0, 0.0, 1.0))
        case '-X':
            return Vector((-1.0, 0.0, 0.0))
        case '-Y':
            return Vector((0.0, -1.0, 0.0))
        case '-Z':
            return Vector((0.0, 0.0, -1.0))


def get_coordinate_system_transform(forward_axis: str = 'X', up_axis: str = 'Z') -> Matrix:
    forward = get_vector_from_axis_identifier(forward_axis)
    up = get_vector_from_axis_identifier(up_axis)
    left = up.cross(forward)
    return Matrix((
        (forward.x, forward.y, forward.z, 0.0),
        (left.x, left.y, left.z, 0.0),
        (up.x, up.y, up.z, 0.0),
        (0.0, 0.0, 0.0, 1.0)
    )).inverted()


def get_mesh_objects_for_collection(collection: Collection) -> Iterable[DfsObject]:
    return filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection))


def get_mesh_objects_for_context(context: Context) -> Iterable[DfsObject]:
    for dfs_object in dfs_view_layer_objects(context.view_layer):
        if dfs_object.obj.type == 'MESH' and dfs_object.is_selected:
            yield dfs_object


def get_armature_for_mesh_objects(mesh_objects: Iterable[Object]) -> Optional[Object]:
    # Ensure that there are either no armature modifiers (static mesh) or that there is exactly one armature modifier
    # object shared between all meshes.
    armature_modifier_objects = set()
    for mesh_object in mesh_objects:
        modifiers = [x for x in mesh_object.modifiers if x.type == 'ARMATURE']
        if len(modifiers) == 0:
            continue
        elif len(modifiers) > 1:
            raise RuntimeError(f'Mesh "{mesh_object.name}" must have only one armature modifier')
        armature_modifier_objects.add(modifiers[0].object)

    if len(armature_modifier_objects) > 1:
        armature_modifier_names = [x.name for x in armature_modifier_objects]
        raise RuntimeError(
            f'All meshes must have the same armature modifier, encountered {len(armature_modifier_names)} ({", ".join(armature_modifier_names)})')
    elif len(armature_modifier_objects) == 1:
        return list(armature_modifier_objects)[0]
    else:
        return None


def _get_psk_input_objects(mesh_objects: Iterable[DfsObject]) -> PskInputObjects:
    mesh_objects = list(mesh_objects)
    if len(mesh_objects) == 0:
        raise RuntimeError('At least one mesh must be selected')

    input_objects = PskInputObjects()
    input_objects.mesh_objects = mesh_objects
    input_objects.armature_object = get_armature_for_mesh_objects([x.obj for x in mesh_objects])

    return input_objects


def get_psk_input_objects_for_context(context: Context) -> PskInputObjects:
    mesh_objects = list(get_mesh_objects_for_context(context))
    return _get_psk_input_objects(mesh_objects)


def get_psk_input_objects_for_collection(collection: Collection, should_exclude_hidden_meshes: bool = True) -> PskInputObjects:
    mesh_objects = get_mesh_objects_for_collection(collection)
    if should_exclude_hidden_meshes:
        mesh_objects = filter(lambda x: x.is_visible, mesh_objects)
    return _get_psk_input_objects(mesh_objects)


class PskBuildResult(object):
    def __init__(self):
        self.psk = None
        self.warnings: List[str] = []


def build_psk(context, input_objects: PskInputObjects, options: PskBuildOptions) -> PskBuildResult:
    armature_object: bpy.types.Object = input_objects.armature_object

    result = PskBuildResult()
    psk = Psk()
    bones = []

    def get_export_space_matrix():
        match options.export_space:
            case 'WORLD':
                return Matrix.Identity(4)
            case 'ARMATURE':
                if armature_object is not None:
                    return armature_object.matrix_world.inverted()
                else:
                    return Matrix.Identity(4)
            case _:
                raise ValueError(f'Invalid export space: {options.export_space}')

    coordinate_system_matrix = get_coordinate_system_transform(options.forward_axis, options.up_axis)
    coordinate_system_default_rotation = coordinate_system_matrix.to_quaternion()

    export_space_matrix = get_export_space_matrix()  # TODO: maybe neutralize the scale here?
    scale_matrix = coordinate_system_matrix @ Matrix.Scale(options.scale, 4)

    if armature_object is None or len(armature_object.data.bones) == 0:
        # If the mesh has no armature object or no bones, simply assign it a dummy bone at the root to satisfy the
        # requirement that a PSK file must have at least one bone.
        psk_bone = Psk.Bone()
        psk_bone.name = bytes('root', encoding='windows-1252')
        psk_bone.flags = 0
        psk_bone.children_count = 0
        psk_bone.parent_index = 0
        psk_bone.location = Vector3.zero()
        psk_bone.rotation = coordinate_system_default_rotation
        psk.bones.append(psk_bone)
    else:
        bone_names = get_export_bone_names(armature_object, options.bone_filter_mode, options.bone_collection_indices)
        armature_data = typing.cast(Armature, armature_object.data)
        bones = [armature_data.bones[bone_name] for bone_name in bone_names]

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
                def get_armature_local_matrix():
                    match options.export_space:
                        case 'WORLD':
                            return armature_object.matrix_world
                        case 'ARMATURE':
                            return Matrix.Identity(4)
                        case _:
                            raise ValueError(f'Invalid export space: {options.export_space}')

                armature_local_matrix = get_armature_local_matrix()
                location = armature_local_matrix @ bone.head
                bone_rotation = bone.matrix.to_quaternion().conjugated()
                local_rotation = armature_local_matrix.to_3x3().to_quaternion().conjugated()
                rotation = bone_rotation @ local_rotation
                rotation.conjugate()
                rotation = coordinate_system_default_rotation @ rotation

            location = scale_matrix @ location

            # If the armature object has been scaled, we need to scale the bone's location to match.
            _, _, armature_object_scale = armature_object.matrix_world.decompose()
            location.x *= armature_object_scale.x
            location.y *= armature_object_scale.y
            location.z *= armature_object_scale.z

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

    # TODO: This wasn't left in a good state. We should detect if we need to add a "default" material.
    #  This can be done by checking if there is an empty material slot on any of the mesh objects, or if there are
    #  no material slots on any of the mesh objects.
    #  If so, it should be added to the end of the list of materials, and its index should mapped to a None value in the
    #  material indices list.
    if len(psk.materials) == 0:
        # Add a default material if no materials are present.
        psk_material = Psk.Material()
        psk_material.name = bytes('None', encoding='windows-1252')
        psk.materials.append(psk_material)

    context.window_manager.progress_begin(0, len(input_objects.mesh_objects))

    material_names = [m.name for m in options.materials]

    for object_index, input_mesh_object in enumerate(input_objects.mesh_objects):

        obj, instance_objects, matrix_world = input_mesh_object.obj, input_mesh_object.instance_objects, input_mesh_object.matrix_world

        should_flip_normals = False

        def get_material_name_indices(obj: Object, material_names: List[str]) -> Iterable[int]:
            '''
            Returns the index of the material in the list of material names.
            If the material is not found, the index 0 is returned.
            '''
            for material_slot in obj.material_slots:
                if material_slot.material is None:
                    yield 0
                else:
                    try:
                        yield material_names.index(material_slot.material.name)
                    except ValueError:
                        yield 0

        # MATERIALS
        material_indices = list(get_material_name_indices(obj, material_names))

        if len(material_indices) == 0:
            # Add a default material if no materials are present.
            material_indices = [0]

        # MESH DATA
        match options.object_eval_state:
            case 'ORIGINAL':
                mesh_object = obj
                mesh_data = obj.data
            case 'EVALUATED':
                # Create a copy of the mesh object after non-armature modifiers are applied.

                # Temporarily force the armature into the rest position.
                # We will undo this later.
                old_pose_position = None
                if armature_object is not None:
                    old_pose_position = armature_object.data.pose_position
                    armature_object.data.pose_position = 'REST'

                depsgraph = context.evaluated_depsgraph_get()
                bm = bmesh.new()

                try:
                    bm.from_object(obj, depsgraph)
                except ValueError:
                    raise RuntimeError(f'Object "{obj.name}" is not evaluated.\n'
                    'This is likely because the object is in a collection that has been excluded from the view layer.')

                mesh_data = bpy.data.meshes.new('')
                bm.to_mesh(mesh_data)
                del bm
                mesh_object = bpy.data.objects.new('', mesh_data)
                mesh_object.matrix_world = matrix_world

                # Extract the scale from the matrix.
                _, _, scale = matrix_world.decompose()

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
                for vertex_group in obj.vertex_groups:
                    mesh_object.vertex_groups.new(name=vertex_group.name)

                # Restore the previous pose position on the armature.
                if old_pose_position is not None:
                    armature_object.data.pose_position = old_pose_position
            case _:
                raise ValueError(f'Invalid object evaluation state: {options.object_eval_state}')

        vertex_offset = len(psk.points)
        matrix_world = scale_matrix @ export_space_matrix @ mesh_object.matrix_world

        # VERTICES
        for vertex in mesh_data.vertices:
            point = Vector3()
            v = matrix_world @ vertex.co
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

            # Keep track of which vertices have been assigned weights.
            # The ones that have not been assigned weights will be assigned to the root bone.
            # Without this, some older versions of UnrealEd may have corrupted meshes.
            vertices_assigned_weights = np.full(len(mesh_data.vertices), False)

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
                    vertices_assigned_weights[vertex_index] = True

            # Assign vertices that have not been assigned weights to the root bone.
            for vertex_index, assigned in enumerate(vertices_assigned_weights):
                if not assigned:
                    w = Psk.Weight()
                    w.bone_index = 0
                    w.point_index = vertex_offset + vertex_index
                    w.weight = 1.0
                    psk.weights.append(w)

        if options.object_eval_state == 'EVALUATED':
            bpy.data.objects.remove(mesh_object)
            bpy.data.meshes.remove(mesh_data)
            del mesh_data

        context.window_manager.progress_update(object_index)

    context.window_manager.progress_end()

    result.psk = psk

    return result
