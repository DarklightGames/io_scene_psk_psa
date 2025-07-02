import bpy
from collections import Counter
from typing import List, Iterable, Optional, Dict, Tuple, cast as typing_cast
from bpy.props import CollectionProperty
from bpy.types import Armature, AnimData, Object
from mathutils import Matrix, Vector, Quaternion as BpyQuaternion
from .data import Vector3, Quaternion
from ..shared.data import PsxBone


def rgb_to_srgb(c: float):
    if c > 0.0031308:
        return 1.055 * (pow(c, (1.0 / 2.4))) - 0.055
    else:
        return 12.92 * c


def get_nla_strips_in_frame_range(animation_data: AnimData, frame_min: float, frame_max: float):
    if animation_data is None:
        return
    for nla_track in animation_data.nla_tracks:
        if nla_track.mute:
            continue
        for strip in nla_track.strips:
            if (strip.frame_start < frame_min and strip.frame_end > frame_max) or \
                    (frame_min <= strip.frame_start < frame_max) or \
                    (frame_min < strip.frame_end <= frame_max):
                yield strip


def populate_bone_collection_list(armature_objects: Iterable[Object], bone_collection_list: CollectionProperty) -> None:
    """
    Updates the bone collections collection.

    Bone collection selections are preserved between updates unless none of the groups were previously selected;
    otherwise, all collections are selected by default.
    """
    has_selected_collections = any([g.is_selected for g in bone_collection_list])
    unassigned_collection_is_selected, selected_assigned_collection_names = True, []

    if not armature_objects:
        return

    if has_selected_collections:
        # Preserve group selections before clearing the list.
        # We handle selections for the unassigned group separately to cover the edge case
        # where there might be an actual group with 'Unassigned' as its name.
        unassigned_collection_idx, unassigned_collection_is_selected = next(iter([
            (i, g.is_selected) for i, g in enumerate(bone_collection_list) if g.index == -1]), (-1, False))

        selected_assigned_collection_names = [
            g.name for i, g in enumerate(bone_collection_list) if i != unassigned_collection_idx and g.is_selected]

    bone_collection_list.clear()

    for armature_object in armature_objects:
        armature = typing_cast(Armature, armature_object.data)

        if armature is None:
            return

        item = bone_collection_list.add()
        item.armature_object_name = armature_object.name
        item.name = 'Unassigned' # TODO: localize
        item.index = -1
        # Count the number of bones without an assigned bone collection
        item.count = sum(map(lambda bone: 1 if len(bone.collections) == 0 else 0, armature.bones))
        item.is_selected = unassigned_collection_is_selected

        for bone_collection_index, bone_collection in enumerate(armature.collections_all):
            item = bone_collection_list.add()
            item.armature_object_name = armature_object.name
            item.name = bone_collection.name
            item.index = bone_collection_index
            item.count = len(bone_collection.bones)
            item.is_selected = bone_collection.name in selected_assigned_collection_names if has_selected_collections else True


def get_export_bone_names(armature_object: Object, bone_filter_mode: str, bone_collection_indices: Iterable[int]) -> List[str]:
    """
    Returns a sorted list of bone indices that should be exported for the given bone filter mode and bone collections.

    Note that the ancestors of bones within the bone collections will also be present in the returned list.

    :param armature_object: Blender object with type `'ARMATURE'`
    :param bone_filter_mode: One of `['ALL', 'BONE_COLLECTIONS']`
    :param bone_collection_indices: A list of bone collection indices to export.
    :return: A sorted list of bone indices that should be exported.
    """
    if armature_object is None or armature_object.type != 'ARMATURE':
        raise ValueError('An armature object must be supplied')

    armature_data = typing_cast(Armature, armature_object.data)
    bones = armature_data.bones
    bone_names = [x.name for x in bones]

    # Get a list of the bone indices that we are explicitly including.
    bone_index_stack = []
    is_exporting_unassigned_bone_collections = -1 in bone_collection_indices
    bone_collections = list(armature_data.collections_all)

    for bone_index, bone in enumerate(bones):
        # Check if this bone is in any of the collections in the bone collection indices list.
        this_bone_collection_indices = set(bone_collections.index(x) for x in bone.collections)
        is_in_exported_bone_collections = len(set(bone_collection_indices).intersection(this_bone_collection_indices)) > 0

        if bone_filter_mode == 'ALL' or \
                (len(bone.collections) == 0 and is_exporting_unassigned_bone_collections) or \
                is_in_exported_bone_collections:
            bone_index_stack.append((bone_index, None))

    # For each bone that is explicitly being added, recursively walk up the hierarchy and ensure that all of
    # those ancestor bone indices are also in the list.
    bone_indices = dict()
    while len(bone_index_stack) > 0:
        bone_index, instigator_bone_index = bone_index_stack.pop()
        bone = bones[bone_index]
        if bone.parent is not None:
            parent_bone_index = bone_names.index(bone.parent.name)
            if parent_bone_index not in bone_indices:
                bone_index_stack.append((parent_bone_index, bone_index))
        bone_indices[bone_index] = instigator_bone_index

    # Sort the bone index list in-place.
    bone_indices = [(x[0], x[1]) for x in bone_indices.items()]
    bone_indices.sort(key=lambda x: x[0])

    # Split out the bone indices and the instigator bone names into separate lists.
    # We use the bone names for the return values because the bone name is a more universal way of referencing them.
    # For example, users of this function may modify bone lists, which would invalidate the indices and require an
    # index mapping scheme to resolve it. Using strings is more comfy and results in less code downstream.
    instigator_bone_names = [bones[x[1]].name if x[1] is not None else None for x in bone_indices]
    bone_names = [bones[x[0]].name for x in bone_indices]

    # Ensure that the hierarchy we are sending back has a single root bone.
    # TODO: This is only relevant if we are exporting a single armature; how should we reorganize this call?
    bone_indices = [x[0] for x in bone_indices]
    root_bones = [bones[bone_index] for bone_index in bone_indices if bones[bone_index].parent is None]
    if len(root_bones) > 1:
        # There is more than one root bone.
        # Print out why each root bone was included by linking it to one of the explicitly included bones.
        root_bone_names = [bone.name for bone in root_bones]
        for root_bone_name in root_bone_names:
            bone_name = root_bone_name
            while True:
                # Traverse the instigator chain until the end to find the true instigator bone.
                # TODO: in future, it would be preferential to have a readout of *all* instigator bones.
                instigator_bone_name = instigator_bone_names[bone_names.index(bone_name)]
                if instigator_bone_name is None:
                    print(f'Root bone "{root_bone_name}" was included because {bone_name} was marked for export')
                    break
                bone_name = instigator_bone_name

        raise RuntimeError('Exported bone hierarchy must have a single root bone.\n'
                           f'The bone hierarchy marked for export has {len(root_bones)} root bones: {root_bone_names}.\n'
                           f'Additional debugging information has been written to the console.')

    return bone_names


def is_bdk_addon_loaded() -> bool:
    return 'bdk' in dir(bpy.ops)


def convert_string_to_cp1252_bytes(string: str) -> bytes:
    try:
        return bytes(string, encoding='windows-1252')
    except UnicodeEncodeError as e:
        raise RuntimeError(f'The string "{string}" contains characters that cannot be encoded in the Windows-1252 codepage') from e


# TODO: Perhaps export space should just be a transform matrix, since the below is not actually used unless we're using WORLD space.
def create_psx_bones_from_blender_bones(
        bones: List[bpy.types.Bone],
        export_space: str = 'WORLD',
        armature_object_matrix_world: Matrix = Matrix.Identity(4),
        scale = 1.0,
        forward_axis: str = 'X',
        up_axis: str = 'Z',
        root_bone: Optional = None,
) -> List[PsxBone]:

    scale_matrix = Matrix.Scale(scale, 4)

    coordinate_system_transform = get_coordinate_system_transform(forward_axis, up_axis)
    coordinate_system_default_rotation = coordinate_system_transform.to_quaternion()

    psx_bones = []
    for bone in bones:
        psx_bone = PsxBone()
        psx_bone.name = convert_string_to_cp1252_bytes(bone.name)

        try:
            parent_index = bones.index(bone.parent)
            psx_bone.parent_index = parent_index
            psx_bones[parent_index].children_count += 1
        except ValueError:
            psx_bone.parent_index = 0

        if bone.parent is not None:
            rotation = bone.matrix.to_quaternion().conjugated()
            inverse_parent_rotation = bone.parent.matrix.to_quaternion().inverted()
            parent_head = inverse_parent_rotation @ bone.parent.head
            parent_tail = inverse_parent_rotation @ bone.parent.tail
            location = (parent_tail - parent_head) + bone.head
        elif bone.parent is None and root_bone is not None:
            # This is a special case for the root bone when export
            # Because the root bone and child bones are in different spaces, we need to treat the root bone of this
            # armature as though it were a child bone.
            bone_rotation = bone.matrix.to_quaternion().conjugated()
            local_rotation = armature_object_matrix_world.to_3x3().to_quaternion().conjugated()
            rotation = bone_rotation @ local_rotation
            translation, _, scale = armature_object_matrix_world.decompose()
            # Invert the scale of the armature object matrix.
            inverse_scale_matrix = Matrix.Identity(4)
            inverse_scale_matrix[0][0] = 1.0 / scale.x
            inverse_scale_matrix[1][1] = 1.0 / scale.y
            inverse_scale_matrix[2][2] = 1.0 / scale.z

            translation = translation @ inverse_scale_matrix
            location = translation + bone.head
        else:
            def get_armature_local_matrix():
                match export_space:
                    case 'WORLD':
                        return armature_object_matrix_world
                    case 'ARMATURE':
                        return Matrix.Identity(4)
                    case 'ROOT':
                        return bone.matrix.inverted()
                    case _:
                        assert False, f'Invalid export space: {export_space}'

            armature_local_matrix = get_armature_local_matrix()
            location = armature_local_matrix @ bone.head
            location = coordinate_system_transform @ location
            bone_rotation = bone.matrix.to_quaternion().conjugated()
            local_rotation = armature_local_matrix.to_3x3().to_quaternion().conjugated()
            rotation = bone_rotation @ local_rotation
            rotation.conjugate()
            rotation = coordinate_system_default_rotation @ rotation

        location = scale_matrix @ location

        # If the armature object has been scaled, we need to scale the bone's location to match.
        _, _, armature_object_scale = armature_object_matrix_world.decompose()
        location.x *= armature_object_scale.x
        location.y *= armature_object_scale.y
        location.z *= armature_object_scale.z

        psx_bone.location.x = location.x
        psx_bone.location.y = location.y
        psx_bone.location.z = location.z

        psx_bone.rotation.w = rotation.w
        psx_bone.rotation.x = rotation.x
        psx_bone.rotation.y = rotation.y
        psx_bone.rotation.z = rotation.z

        psx_bones.append(psx_bone)

    return psx_bones


class PsxBoneCreateResult:
    def __init__(self,
                 bones: List[Tuple[PsxBone, Optional[Object]]],  # List of tuples of (psx_bone, armature_object)
                 armature_object_root_bone_indices: Dict[Object, int],
                 armature_object_bone_names: Dict[Object, List[str]],
                 ):
        self.bones = bones
        self.armature_object_root_bone_indices = armature_object_root_bone_indices
        self.armature_object_bone_names = armature_object_bone_names
    
    @property
    def has_false_root_bone(self) -> bool:
        return len(self.bones) > 0 and self.bones[0][1] is None


def convert_bpy_quaternion_to_psx_quaternion(other: BpyQuaternion) -> Quaternion:
    quaternion = Quaternion()
    quaternion.x = other.x
    quaternion.y = other.y
    quaternion.z = other.z
    quaternion.w = other.w
    return quaternion


def create_psx_bones(
        armature_objects: List[Object],
        export_space: str = 'WORLD',
        root_bone_name: str = 'ROOT',
        forward_axis: str = 'X',
        up_axis: str = 'Z',
        scale: float = 1.0,
        bone_filter_mode: str = 'ALL',
        bone_collection_indices: Optional[List[Tuple[str, int]]] = None,
) -> PsxBoneCreateResult:
    """
    Creates a list of PSX bones from the given armature objects and options.
    This function will throw a RuntimeError if multiple armature objects are passed in and the export space is not WORLD.
    It will also throw a RuntimeError if the bone names are not unique when compared case-insensitively.
    """
    if bone_collection_indices is None:
        bone_collection_indices = []

    bones: List[Tuple[PsxBone, Optional[Object]]] = []

    if export_space != 'WORLD' and len(armature_objects) > 1:
        armature_object_names = [armature_object.name for armature_object in armature_objects]
        raise RuntimeError(f'When exporting multiple armatures, the Export Space must be World. The following armatures are attempting to be exported: {armature_object_names}')

    coordinate_system_matrix = get_coordinate_system_transform(forward_axis, up_axis)
    coordinate_system_default_rotation = coordinate_system_matrix.to_quaternion()

    total_bone_count = sum(len(armature_object.data.bones) for armature_object in armature_objects)


    # Store the bone names to be exported for each armature object.
    armature_object_bone_names: Dict[Object, List[str]] = dict()
    for armature_object in  armature_objects:
        armature_bone_collection_indices = [x[1] for x in bone_collection_indices if x[0] == armature_object.name]
        bone_names = get_export_bone_names(armature_object, bone_filter_mode, armature_bone_collection_indices)
        armature_object_bone_names[armature_object] = bone_names

    # Store the index of the root bone for each armature object.
    # We will need this later to correctly assign vertex weights.
    armature_object_root_bone_indices: Dict[Optional[Object], int] = dict()

    if len(armature_objects) == 0 or total_bone_count == 0:
        # If the mesh has no armature object or no bones, simply assign it a dummy bone at the root to satisfy the
        # requirement that a PSK file must have at least one bone.
        psx_bone = PsxBone()
        psx_bone.name = convert_string_to_cp1252_bytes(root_bone_name)
        psx_bone.flags = 0
        psx_bone.children_count = 0
        psx_bone.parent_index = 0
        psx_bone.location = Vector3.zero()
        psx_bone.rotation = convert_bpy_quaternion_to_psx_quaternion(coordinate_system_default_rotation)
        bones.append((psx_bone, None))

        armature_object_root_bone_indices[None] = 0
    else:
        # If we have multiple armature objects, create a root bone at the world origin.
        if len(armature_objects) > 1:
            psx_bone = PsxBone()
            psx_bone.name = convert_string_to_cp1252_bytes(root_bone_name)
            psx_bone.flags = 0
            psx_bone.children_count = total_bone_count
            psx_bone.parent_index = 0
            psx_bone.location = Vector3.zero()
            psx_bone.rotation = convert_bpy_quaternion_to_psx_quaternion(coordinate_system_default_rotation)
            bones.append((psx_bone, None))

            armature_object_root_bone_indices[None] = 0

        root_bone = bones[0][0] if len(bones) > 0 else None

        for armature_object in armature_objects:
            bone_names = armature_object_bone_names[armature_object]
            armature_data = typing_cast(Armature, armature_object.data)
            armature_bones = [armature_data.bones[bone_name] for bone_name in bone_names]

            armature_psx_bones = create_psx_bones_from_blender_bones(
                bones=armature_bones,
                export_space=export_space,
                armature_object_matrix_world=armature_object.matrix_world,
                scale=scale,
                forward_axis=forward_axis,
                up_axis=up_axis,
                root_bone=root_bone,
            )

            # If we are appending these bones to an existing list of bones, we need to adjust the parent indices for
            # all the non-root bones.
            if len(bones) > 0:
                parent_index_offset = len(bones)
                for bone in armature_psx_bones[1:]:
                    bone.parent_index += parent_index_offset

            armature_object_root_bone_indices[armature_object] = len(bones)

            bones.extend((psx_bone, armature_object) for psx_bone in armature_psx_bones)

    # Check if there are bone name conflicts between armatures.
    bone_name_counts = Counter(bone[0].name.decode('windows-1252').upper() for bone in bones)
    for bone_name, count in bone_name_counts.items():
        if count > 1:
            error_message = f'Found {count} bones with the name "{bone_name}". '
            f'Bone names must be unique when compared case-insensitively.'

            if len(armature_objects) > 1 and bone_name == root_bone_name.upper():
                error_message += f' This is the name of the automatically generated root bone. Consider changing this '
                f''
                raise RuntimeError(error_message)

    return PsxBoneCreateResult(
        bones=bones,
        armature_object_root_bone_indices=armature_object_root_bone_indices,
        armature_object_bone_names=armature_object_bone_names,
    )


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
        case _:
            assert False, f'Invalid axis identifier: {axis_identifier}'


def get_coordinate_system_transform(forward_axis: str = 'X', up_axis: str = 'Z') -> Matrix:
    forward = get_vector_from_axis_identifier(forward_axis)
    up = get_vector_from_axis_identifier(up_axis)
    left = up.cross(forward)
    return Matrix((
        (forward.x, forward.y, forward.z, 0.0),
        (left.x, left.y, left.z, 0.0),
        (up.x, up.y, up.z, 0.0),
        (0.0, 0.0, 0.0, 1.0)
    ))
