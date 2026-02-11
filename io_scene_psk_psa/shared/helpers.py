import bpy
from collections import Counter
from typing import Iterable, cast as typing_cast
from bpy.types import Armature, AnimData, Collection, Context, Object, ArmatureModifier, SpaceProperties, PropertyGroup, Material
from mathutils import Matrix, Vector, Quaternion as BpyQuaternion
from psk_psa_py.shared.data import PsxBone, Quaternion, Vector3

from ..shared.types import BpyCollectionProperty, PSX_PG_bone_collection_list_item


def rgb_to_srgb(c: float) -> float:
    if c > 0.0031308:
        return 1.055 * (pow(c, (1.0 / 2.4))) - 0.055
    return 12.92 * c


def get_nla_strips_in_frame_range(animation_data: AnimData, frame_min: float, frame_max: float):
    for nla_track in animation_data.nla_tracks:
        if nla_track.mute:
            continue
        for strip in nla_track.strips:
            if (strip.frame_start < frame_min and strip.frame_end > frame_max) or \
                    (frame_min <= strip.frame_start < frame_max) or \
                    (frame_min < strip.frame_end <= frame_max):
                yield strip


def populate_bone_collection_list(
        bone_collection_list: BpyCollectionProperty[PSX_PG_bone_collection_list_item], 
        armature_objects: Iterable[Object],
        primary_key: str = 'OBJECT'
        ):
    """
    Updates the bone collection list.

    Selection is preserved between updates unless none of the groups were previously selected.
    Otherwise, all collections are selected by default.

    The primary key is used to determine how to group the armature objects. For example, if the primary key is
    'DATA', then all bone collections with the same armature data-block will be under one entry.

    :param bone_collection_list: The list to update.
    :param armature_objects: The armature objects to populate the collection with.
    :param primary_key: The primary key to use for the collection (one of 'OBJECT' or 'DATA').
    :return: None
    """
    has_selected_collections = any([g.is_selected for g in bone_collection_list])
    unassigned_collection_is_selected, selected_assigned_collection_names = True, []

    if primary_key not in ('OBJECT', 'DATA'):
        assert False, f'Invalid primary key: {primary_key}'

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

    unique_armature_data = set()

    for armature_object in armature_objects:
        armature_data = typing_cast(Armature, armature_object.data)

        if armature_data is None:
            continue

        if primary_key == 'DATA':
            if armature_data in unique_armature_data:
                # Skip this armature since we have already added an entry for it and we are using the data as the key.
                continue
            unique_armature_data.add(armature_data)
        
        unassigned_bone_count = sum(map(lambda bone: 1 if len(bone.collections) == 0 else 0, armature_data.bones))

        if unassigned_bone_count > 0:
            item = bone_collection_list.add()
            item.armature_object_name = armature_object.name
            item.armature_data_name = armature_data.name if armature_data else ''
            item.name = 'Unassigned'
            item.index = -1
            # Count the number of bones without an assigned bone collection
            item.count = unassigned_bone_count
            item.is_selected = unassigned_collection_is_selected

        for bone_collection_index, bone_collection in enumerate(armature_data.collections_all):
            item = bone_collection_list.add()
            item.armature_object_name = armature_object.name
            item.armature_data_name = armature_data.name if armature_data else ''
            item.name = bone_collection.name
            item.index = bone_collection_index
            item.count = len(bone_collection.bones)
            item.is_selected = bone_collection.name in selected_assigned_collection_names if has_selected_collections else True


def get_export_bone_names(armature_object: Object, bone_filter_mode: str, bone_collection_indices: Iterable[int]) -> list[str]:
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
    bone_names = [bones[x[0]].name for x in bone_indices]

    return bone_names


def is_bdk_addon_loaded() -> bool:
    return 'bdk' in dir(bpy.ops)


def convert_string_to_cp1252_bytes(string: str) -> bytes:
    try:
        return bytes(string, encoding='windows-1252')
    except UnicodeEncodeError as e:
        raise RuntimeError(f'The string "{string}" contains characters that cannot be encoded in the Windows-1252 codepage') from e


def create_psx_bones_from_blender_bones(
        bones: list[bpy.types.Bone],
        armature_object_matrix_world: Matrix,
) -> list[PsxBone]:
    """
    Creates PSX bones from the given Blender bones.
    
    The bones are in world space based on the armature object's world matrix.
    """
    # Apply the scale of the armature object to the bone location.
    _, _, armature_object_scale = armature_object_matrix_world.decompose()

    psx_bones: list[PsxBone] = []
    for bone in bones:
        psx_bone = PsxBone()
        psx_bone.name = convert_string_to_cp1252_bytes(bone.name)

        if bone.parent is not None:
            try:
                parent_index = bones.index(bone.parent)
                psx_bone.parent_index = parent_index
                psx_bones[parent_index].children_count += 1
            except ValueError:
                pass

        if bone.parent is not None:
            # Child bone.
            rotation = bone.matrix.to_quaternion().conjugated()
            inverse_parent_rotation = bone.parent.matrix.to_quaternion().inverted()
            parent_head = inverse_parent_rotation @ bone.parent.head
            parent_tail = inverse_parent_rotation @ bone.parent.tail
            location = (parent_tail - parent_head) + bone.head
        else:
            location = armature_object_matrix_world @ bone.head
            bone_rotation = bone.matrix.to_quaternion().conjugated()
            rotation = bone_rotation @ armature_object_matrix_world.to_3x3().to_quaternion()
            rotation.conjugate()

        location.x *= armature_object_scale.x
        location.y *= armature_object_scale.y
        location.z *= armature_object_scale.z

        # Copy the calculated location and rotation to the bone.
        psx_bone.location = convert_vector_to_vector3(location)
        psx_bone.rotation = convert_bpy_quaternion_to_psx_quaternion(rotation)

        psx_bones.append(psx_bone)

    return psx_bones


class PsxBoneResult:
    def __init__(self, psx_bone: PsxBone, armature_object: Object | None) -> None:
        self.psx_bone: PsxBone = psx_bone
        self.armature_object: Object | None = armature_object


class PsxBoneCreateResult:
    def __init__(self,
                 bones: list[PsxBoneResult],  # List of tuples of (psx_bone, armature_object)
                 armature_object_root_bone_indices: dict[Object, int],
                 armature_object_bone_names: dict[Object, list[str]],
                 ):
        self.bones = bones
        self.armature_object_root_bone_indices = armature_object_root_bone_indices
        self.armature_object_bone_names = armature_object_bone_names


def convert_vector_to_vector3(vector: Vector) -> Vector3:
    """
    Convert a Blender mathutils.Vector to a psk_psa_py Vector3.
    """
    vector3 = Vector3()
    vector3.x = vector.x
    vector3.y = vector.y
    vector3.z = vector.z
    return vector3


def convert_bpy_quaternion_to_psx_quaternion(quaternion: BpyQuaternion) -> Quaternion:
    """
    Convert a Blender mathutils.Quaternion to a psk_psa_py Quaternion.
    """
    psx_quaternion = Quaternion()
    psx_quaternion.x = quaternion.x
    psx_quaternion.y = quaternion.y
    psx_quaternion.z = quaternion.z
    psx_quaternion.w = quaternion.w
    return psx_quaternion


class PsxBoneCollection:
    """
    Stores the armature's object name, data-block name and bone collection index.
    """
    def __init__(self, armature_object_name: str, armature_data_name: str, index: int):
        self.armature_object_name = armature_object_name
        self.armature_data_name = armature_data_name
        self.index = index


class ObjectNode:
    def __init__(self, obj: Object):
        self.object = obj
        self.parent: ObjectNode | None = None
        self.children: list[ObjectNode] = []
    
    @property
    def root(self):
        """
        Gets the root in the object hierarchy. This can return itself if this node has no parent.
        """
        n = self
        while n.parent is not None:
            n = n.parent
        return n


class ObjectTree:
    '''
    A tree of the armature objects based on their hierarchy.
    '''
    def __init__(self, objects: Iterable[Object]):
        self.root_nodes: list[ObjectNode] = []
        object_node_map: dict[Object, ObjectNode] = {x: ObjectNode(x) for x in objects}
        
        for obj, object_node in object_node_map.items():
            if obj.parent in object_node_map:
                parent_node = object_node_map[obj.parent]
                object_node.parent = parent_node
                parent_node.children.append(object_node)
            else:
                self.root_nodes.append(object_node)

    def __iter__(self):
        """
        An depth-first iterator over the armature tree.
        """
        node_stack = [] + self.root_nodes
        while node_stack:
            node = node_stack.pop()
            yield node
            node_stack = node.children + node_stack
    
    def objects_iterator(self):
        for node in self:
            yield node.object
    
    def dump(self):
        # Print out the hierarchy of armature objects for debugging using the root nodes, with indentation to show parent-child relationships.
        for root_node in self.root_nodes:
            def print_object_node(node: ObjectNode, indent: int = 0):
                print(' ' * indent + f'- {node.object.name}')
                for child_node in node.children:
                    print_object_node(child_node, indent + 2)
            print_object_node(root_node)


def create_psx_bones(
        armature_objects: list[Object],
        export_space: str = 'WORLD',
        root_bone_name: str = 'ROOT',
        forward_axis: str = 'X',
        up_axis: str = 'Z',
        scale: float = 1.0,
        bone_filter_mode: str = 'ALL',
        bone_collection_indices: list[PsxBoneCollection] | None = None,
        bone_collection_primary_key: str = 'OBJECT',
) -> PsxBoneCreateResult:
    """
    Creates a list of PSX bones from the given armature objects and options.
    This function will throw a RuntimeError if multiple armature objects are passed in and the export space is not WORLD.
    It will also throw a RuntimeError if the bone names are not unique when compared case-insensitively.
    """
    if bone_collection_indices is None:
        bone_collection_indices = []

    armature_tree = ObjectTree(armature_objects)

    if len(armature_tree.root_nodes) >= 2:
        raise RuntimeError(
            'Multiple root armature objects were found. '
            'Only one root armature object is allowed. '
            'To use multiple armature objects, parent them to one another in a hierarchy using Bone parenting.'
        )

    # TODO: confirm this to be working with non-bone parented armature hierarchies.

    total_bone_count = 0
    for armature_object in filter(lambda x: x.data is not None, armature_objects):
        armature_data = typing_cast(Armature, armature_object.data)
        total_bone_count += len(armature_data.bones)

    # Store the bone names to be exported for each armature object.
    armature_object_bone_names: dict[Object, list[str]] = dict()
    for armature_object in  armature_objects:
        armature_bone_collection_indices: list[int] = []
        match bone_collection_primary_key:
            case 'OBJECT':
                armature_bone_collection_indices.extend([x.index for x in bone_collection_indices if x.armature_object_name == armature_object.name])
            case 'DATA':
                armature_bone_collection_indices.extend([x.index for x in bone_collection_indices if armature_object.data and x.armature_data_name == armature_object.data.name])
            case _:
                assert False, f'Invalid primary key: {bone_collection_primary_key}'
        bone_names = get_export_bone_names(armature_object, bone_filter_mode, armature_bone_collection_indices)
        armature_object_bone_names[armature_object] = bone_names

    # Store the index of the root bone for each armature object.
    # We will need this later to correctly assign vertex weights.
    armature_object_root_bone_indices: dict[Object | None, int] = dict()
    bones: list[PsxBoneResult] = []

    # Iterate through all the armature objects.
    for armature_object in armature_objects:
        bone_names = armature_object_bone_names[armature_object]
        armature_data = typing_cast(Armature, armature_object.data)
        armature_bones = [armature_data.bones[bone_name] for bone_name in bone_names]

        # Ensure that we don't have multiple root bones in this armature.
        root_bone_count = sum(1 for bone in armature_bones if bone.parent is None)
        if root_bone_count > 1:
            raise RuntimeError(f'Armature object \'{armature_object.name}\' has multiple root bones. '
                               f'Only one root bone is allowed per armature.'
                               )

        armature_psx_bones = create_psx_bones_from_blender_bones(
            bones=armature_bones,
            armature_object_matrix_world=armature_object.matrix_world,
        )

        if len(armature_psx_bones) == 0:
            continue

        # We have the bones in world space. If we are attaching this armature to a parent bone, we need to convert
        # the root bone to be relative to the target parent bone.
        if armature_object.parent in armature_objects:
            match armature_object.parent_type:
                case 'BONE':
                    # Parent to a bone in the parent armature object.
                    # We just need to get the world-space location of each of the bones and get the relative pose, then
                    # assign that location and rotation to the root bone.
                    parent_bone_name = armature_object.parent_bone

                    if parent_bone_name == '':
                        raise RuntimeError(f'Armature object \'{armature_object.name}\' is parented to a bone but no parent bone name is specified.')

                    parent_armature_data = typing_cast(Armature, armature_object.parent.data)
                    if parent_armature_data is None:
                        raise RuntimeError(f'Parent object \'{armature_object.parent.name}\' is not an armature.')
                    try:
                        parent_bone = parent_armature_data.bones[parent_bone_name]
                    except KeyError:
                        raise RuntimeError(f'Bone \'{parent_bone_name}\' could not be found in armature \'{armature_object.parent.name}\'.')    
                    
                    parent_bone_world_matrix = armature_object.parent.matrix_world @ parent_bone.matrix_local.to_4x4()
                    parent_bone_world_location, parent_bone_world_rotation, _ = parent_bone_world_matrix.decompose()

                    # Convert the root bone location to be relative to the parent bone.
                    root_bone = armature_psx_bones[0]
                    root_bone_location = Vector((root_bone.location.x, root_bone.location.y, root_bone.location.z))
                    relative_location = parent_bone_world_rotation.inverted() @ (root_bone_location - parent_bone_world_location)
                    root_bone.location = convert_vector_to_vector3(relative_location)
                    # Convert the root bone rotation to be relative to the parent bone.
                    root_bone_rotation = BpyQuaternion((root_bone.rotation.w, root_bone.rotation.x, root_bone.rotation.y, root_bone.rotation.z))
                    relative_rotation = parent_bone_world_rotation.inverted() @ root_bone_rotation
                    root_bone.rotation = convert_bpy_quaternion_to_psx_quaternion(relative_rotation)
                case _:
                    raise RuntimeError(f'Unhandled parent type ({armature_object.parent_type}) for object {armature_object.name}.\n'
                                        f'Parent type must be \'Bone\'.'
                                        )

        # If we are appending these bones to an existing list of bones, we need to adjust the parent indices for
        # all the non-root bones.
        if len(bones) > 0:
            parent_index_offset = len(bones)
            for bone in armature_psx_bones[1:]:
                bone.parent_index += parent_index_offset

        armature_object_root_bone_indices[armature_object] = len(bones)

        bones.extend(PsxBoneResult(psx_bone, armature_object) for psx_bone in armature_psx_bones)

    # Check if any of the armatures are parented to one another.
    # If so, adjust the hierarchy as though they are part of the same armature object.
    # This will let us re-use rig components without destructively joining them.
    for armature_object in armature_objects:
        if armature_object.parent not in armature_objects:
            continue

        # This armature object is parented to another armature object that we are exporting.
        # First fetch the root bone indices for the two armature objects.
        root_bone_index = armature_object_root_bone_indices.get(armature_object, None)
        parent_root_bone_index = armature_object_root_bone_indices.get(armature_object.parent, None)

        if root_bone_index is None or parent_root_bone_index is None:
            raise RuntimeError(f'Could not find root bone index for armature object \'{armature_object.name}\' or its parent \'{armature_object.parent.name}\'.\n'
                               'This likely means that one of the armatures does not have any bones that are being exported, which is not allowed when using armature parenting between multiple armatures.'
                               )

        match armature_object.parent_type:
            case 'OBJECT':
                # Parent this armature's root bone to the root bone of the parent object.
                bones[root_bone_index].psx_bone.parent_index = parent_root_bone_index
            case 'BONE':
                # Parent this armature's root bone to the specified bone in the parent.
                new_parent_index = None
                for bone_index, bone in enumerate(bones):
                    if bone.psx_bone.name == convert_string_to_cp1252_bytes(armature_object.parent_bone) and bone.armature_object == armature_object.parent:
                        new_parent_index = bone_index
                        break
                if new_parent_index == None:
                    raise RuntimeError(f'Bone \'{armature_object.parent_bone}\' could not be found in armature \'{armature_object.parent.name}\'.')
                bones[root_bone_index].psx_bone.parent_index = new_parent_index
            case _:
                raise RuntimeError(f'Unhandled parent type ({armature_object.parent_type}) for object {armature_object.name}.\n'
                                    f'Parent type must be \'Object\' or \'Bone\'.'
                                    )

    match export_space:
        case 'WORLD':
            # No action needed, bones are already in world space.
            pass
        case 'ARMATURE':
            # The bone is in world-space. We need to convert it to armature (object) space.
            # Get this from matrix_local.
            root_bone, root_bone_armature_object = bones[0].psx_bone, bones[0].armature_object
            if root_bone_armature_object is None:
                raise RuntimeError('Cannot export to Armature space when multiple armatures are being exported.')
        
            armature_data = typing_cast(Armature, root_bone_armature_object.data)
            matrix_local = armature_data.bones[root_bone.name.decode('windows-1252')].matrix_local
            location, rotation, _ = matrix_local.decompose()
            root_bone.location = convert_vector_to_vector3(location)
            root_bone.rotation = convert_bpy_quaternion_to_psx_quaternion(rotation)
        case 'ROOT':
            # Zero out the root bone transforms.
            root_bone = bones[0].psx_bone
            root_bone.location = Vector3.zero()
            root_bone.rotation = Quaternion.identity()
        case _:
            assert False, f'Invalid export space: {export_space}'

    # Check if there are bone name conflicts between armatures.
    bone_name_counts = Counter(bone.psx_bone.name.decode('windows-1252').upper() for bone in bones)
    for bone_name, count in bone_name_counts.items():
        if count > 1:
            error_message = f'Found {count} bones with the name "{bone_name}". '
            f'Bone names must be unique when compared case-insensitively.'

            if len(armature_objects) > 1 and bone_name == root_bone_name.upper():
                error_message += f' This is the name of the automatically generated root bone. Consider changing this '
                f''
                raise RuntimeError(error_message)
    
    # Apply the scale to the bone locations.
    for bone in bones:
        bone.psx_bone.location.x *= scale
        bone.psx_bone.location.y *= scale
        bone.psx_bone.location.z *= scale
    
    coordinate_system_matrix = get_coordinate_system_transform(forward_axis, up_axis)
    coordinate_system_default_rotation = coordinate_system_matrix.to_quaternion()

    # Apply the coordinate system transform to the root bone.
    root_psx_bone = bones[0].psx_bone
    # Get transform matrix from root bone location and rotation.
    root_bone_location = Vector((root_psx_bone.location.x, root_psx_bone.location.y, root_psx_bone.location.z))
    root_bone_rotation = BpyQuaternion((root_psx_bone.rotation.w, root_psx_bone.rotation.x, root_psx_bone.rotation.y, root_psx_bone.rotation.z))
    root_bone_matrix = (
        Matrix.Translation(root_bone_location) @
        root_bone_rotation.to_matrix().to_4x4()
    )
    root_bone_matrix = coordinate_system_default_rotation.inverted().to_matrix().to_4x4() @ root_bone_matrix
    location, rotation, _ = root_bone_matrix.decompose()
    root_psx_bone.location = convert_vector_to_vector3(location)
    root_psx_bone.rotation = convert_bpy_quaternion_to_psx_quaternion(rotation)

    convert_bpy_quaternion_to_psx_quaternion(coordinate_system_default_rotation)

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


def get_armatures_for_mesh_objects(mesh_objects: Iterable[Object]):
    """
    Returns a generator of unique armature objects that are used by the given mesh objects.
    """
    armature_objects: set[Object] = set()
    for mesh_object in mesh_objects:
        armature_modifiers = [typing_cast(ArmatureModifier, x) for x in mesh_object.modifiers if x.type == 'ARMATURE']
        for armature_object in map(lambda x: x.object, armature_modifiers):
            if armature_object is not None:
                armature_objects.add(armature_object)
    yield from armature_objects


def get_collection_from_context(context: Context) -> Collection | None:
    if context.space_data is None or context.space_data.type != 'PROPERTIES':
        return None
    space_data = typing_cast(SpaceProperties, context.space_data)
    if space_data.use_pin_id:
        return typing_cast(Collection, space_data.pin_id)
    else:
        return context.collection


def get_collection_export_operator_from_context(context: Context) -> PropertyGroup | None:
    collection = get_collection_from_context(context)
    if collection is None or collection.active_exporter_index is None:
        return None
    if 0 > collection.active_exporter_index >= len(collection.exporters):
        return None
    exporter = collection.exporters[collection.active_exporter_index]
    return exporter.export_properties


from ..shared.dfs import DfsObject, dfs_collection_objects, dfs_view_layer_objects
from typing import Set
from bpy.types import Depsgraph


class PskInputObjects(object):
    def __init__(self):
        self.mesh_dfs_objects: list[DfsObject] = []
        self.armature_objects: list[Object] = []


def get_materials_for_mesh_objects(depsgraph: Depsgraph, mesh_objects: Iterable[Object]):
    '''
    Yields unique materials used by the given mesh objects.
    If any mesh has no material slots or any empty material slots, None is yielded at the end.
    '''
    yielded_materials: Set[Material] = set()
    has_none_material = False
    for mesh_object in mesh_objects:
        evaluated_mesh_object = mesh_object.evaluated_get(depsgraph)
        # Check if mesh has no material slots or any empty material slots
        if len(evaluated_mesh_object.material_slots) == 0:
            has_none_material = True
        else:
            for material_slot in evaluated_mesh_object.material_slots:
                material = material_slot.material
                if material is None:
                    has_none_material = True
                else:
                    if material not in yielded_materials:
                        yielded_materials.add(material)
                        yield material
    # Yield None at the end if any mesh had no material slots or empty material slots
    if has_none_material:
        yield None


def get_mesh_objects_for_collection(collection: Collection) -> Iterable[DfsObject]:
    return filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection))


def get_mesh_objects_for_context(context: Context) -> Iterable[DfsObject]:
    if context.view_layer is None:
        return
    for dfs_object in dfs_view_layer_objects(context.view_layer):
        if dfs_object.obj.type == 'MESH' and dfs_object.is_selected:
            yield dfs_object


def get_armature_for_mesh_object(mesh_object: Object) -> Object | None:
    if mesh_object.type != 'MESH':
        return None
    # Get the first armature modifier with a non-empty armature object.
    for modifier in filter(lambda x: x.type == 'ARMATURE', mesh_object.modifiers):
            armature_modifier = typing_cast(ArmatureModifier, modifier)
            if armature_modifier.object is not None:
                return armature_modifier.object
    return None


def _get_psk_input_objects(mesh_dfs_objects: Iterable[DfsObject]) -> PskInputObjects:
    mesh_dfs_objects = list(mesh_dfs_objects)
    if len(mesh_dfs_objects) == 0:
        raise RuntimeError('No mesh objects were found to export.')
    input_objects = PskInputObjects()
    input_objects.mesh_dfs_objects = mesh_dfs_objects
    # Get the armature objects used on all the meshes being exported.
    armature_objects = get_armatures_for_mesh_objects(map(lambda x: x.obj, mesh_dfs_objects))
    # Sort them in hierarchy order.
    input_objects.armature_objects = list(ObjectTree(armature_objects).objects_iterator())
    return input_objects


def get_psk_input_objects_for_context(context: Context) -> PskInputObjects:
    mesh_objects = list(get_mesh_objects_for_context(context))
    return _get_psk_input_objects(mesh_objects)


def get_psk_input_objects_for_collection(collection: Collection) -> PskInputObjects:
    mesh_objects = get_mesh_objects_for_collection(collection)
    return _get_psk_input_objects(mesh_objects)
