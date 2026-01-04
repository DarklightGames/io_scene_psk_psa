import bpy
from collections import Counter
from typing import List, Iterable, Optional, Dict, Tuple, cast as typing_cast
from bpy.types import Armature, AnimData, Collection, Context, Object, ArmatureModifier, SpaceProperties, PropertyGroup
from mathutils import Matrix, Vector, Quaternion as BpyQuaternion
from psk_psa_py.shared.data import PsxBone, Quaternion

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
        armature = typing_cast(Armature, armature_object.data)

        if armature is None:
            continue

        if primary_key == 'DATA' and armature_object.data in unique_armature_data:
            # Skip this armature since we have already added an entry for it and we are using the data as the key.
            continue
    
        unique_armature_data.add(armature_object.data)

        item = bone_collection_list.add()
        item.armature_object_name = armature_object.name
        item.armature_data_name = armature_object.data.name if armature_object.data else ''
        item.name = 'Unassigned' # TODO: localize
        item.index = -1
        # Count the number of bones without an assigned bone collection
        item.count = sum(map(lambda bone: 1 if len(bone.collections) == 0 else 0, armature.bones))
        item.is_selected = unassigned_collection_is_selected

        for bone_collection_index, bone_collection in enumerate(armature.collections_all):
            item = bone_collection_list.add()
            item.armature_object_name = armature_object.name
            item.armature_data_name = armature_object.data.name if armature_object.data else ''
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
    bone_names = [bones[x[0]].name for x in bone_indices]

    # instigator_bone_names = [bones[x[1]].name if x[1] is not None else None for x in bone_indices]
    # # Ensure that the hierarchy we are sending back has a single root bone.
    # # TODO: This is only relevant if we are exporting a single armature; how should we reorganize this call?
    # bone_indices = [x[0] for x in bone_indices]
    # root_bones = [bones[bone_index] for bone_index in bone_indices if bones[bone_index].parent is None]
    # if len(root_bones) > 1:
    #     # There is more than one root bone.
    #     # Print out why each root bone was included by linking it to one of the explicitly included bones.
    #     root_bone_names = [bone.name for bone in root_bones]
    #     for root_bone_name in root_bone_names:
    #         bone_name = root_bone_name
    #         while True:
    #             # Traverse the instigator chain until the end to find the true instigator bone.
    #             # TODO: in future, it would be preferential to have a readout of *all* instigator bones.
    #             instigator_bone_name = instigator_bone_names[bone_names.index(bone_name)]
    #             if instigator_bone_name is None:
    #                 print(f'Root bone "{root_bone_name}" was included because {bone_name} was marked for export')
    #                 break
    #             bone_name = instigator_bone_name

    #     raise RuntimeError('Exported bone hierarchy must have a single root bone.\n'
    #                        f'The bone hierarchy marked for export has {len(root_bones)} root bones: {root_bone_names}.\n'
    #                        f'Additional debugging information has been written to the console.')

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
        root_bone: PsxBone | None = None
) -> List[PsxBone]:

    scale_matrix = Matrix.Scale(scale, 4)

    coordinate_system_transform = get_coordinate_system_transform(forward_axis, up_axis)
    coordinate_system_default_rotation = coordinate_system_transform.to_quaternion()

    psx_bones = []
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

        # TODO: Need to add handling here for case where the root is being parented to another armature.
        # In that case, we need to convert the root bone from world space to the local space of the target bone.
        # I think we actually have an opportunity to make this more understandable. If we pass the root_bone in here,
        # we can handle both cases in the same logic, since `root_bone` is assumed to be at origin currently.
        # `root_bone` could be changed to be (Bone, Object) tuple?

        if bone.parent is not None:
            # Child bone.
            rotation = bone.matrix.to_quaternion().conjugated()
            inverse_parent_rotation = bone.parent.matrix.to_quaternion().inverted()
            parent_head = inverse_parent_rotation @ bone.parent.head
            parent_tail = inverse_parent_rotation @ bone.parent.tail
            location = (parent_tail - parent_head) + bone.head
        else:  # bone.parent is None
            if root_bone is not None:
                # This is a special case for when a root bone is being passed.
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
                # Parent is none AND there is no special root bone.
                # This is the default case for the root bone of single-armature exports.
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

        # Copy the calculated location and rotation to the bone.
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
        self.children: List['ObjectNode'] = []


class ObjectTree:
    def __init__(self) -> None:
        self.root_nodes: List[ObjectNode] = []
    
    @staticmethod
    def from_objects(objects: Iterable[Object]) -> 'ObjectTree':
        '''
        Make a tree of the armature objects based on their hierarchy.
        '''
        tree = ObjectTree()
        object_node_map: Dict[Object, ObjectNode] = {x: ObjectNode(x) for x in objects}
        
        for obj, object_node in object_node_map.items():
            if obj.parent in object_node_map:
                parent_node = object_node_map[obj.parent]
                parent_node.children.append(object_node)
            else:
                tree.root_nodes.append(object_node)

        return tree

    def __iter__(self):
        """
        An depth-first iterator over the armature tree.
        """
        node_stack = self.root_nodes
        while node_stack:
            node = node_stack.pop()
            yield node
            node_stack = node.children + node_stack
    
    def objects_dfs(self):
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
        armature_objects: List[Object],
        export_space: str = 'WORLD',
        root_bone_name: str = 'ROOT',
        forward_axis: str = 'X',
        up_axis: str = 'Z',
        scale: float = 1.0,
        bone_filter_mode: str = 'ALL',
        bone_collection_indices: Optional[List[PsxBoneCollection]] = None,
        bone_collection_primary_key: str = 'OBJECT',
) -> PsxBoneCreateResult:
    """
    Creates a list of PSX bones from the given armature objects and options.
    This function will throw a RuntimeError if multiple armature objects are passed in and the export space is not WORLD.
    It will also throw a RuntimeError if the bone names are not unique when compared case-insensitively.
    """
    if bone_collection_indices is None:
        bone_collection_indices = []

    armature_tree = ObjectTree.from_objects(armature_objects)

    # Check that there is only one root bone. If there are multiple armature objects, the export space must be WORLD.
    if len(armature_tree.root_nodes) >= 2 and export_space != 'WORLD':
        root_armature_names = [node.object.name for node in armature_tree.root_nodes]
        raise RuntimeError(f'When exporting multiple armatures, the Export Space must be World.\n' \
            f'The following armatures are attempting to be exported: {root_armature_names}')

    coordinate_system_matrix = get_coordinate_system_transform(forward_axis, up_axis)
    coordinate_system_default_rotation = coordinate_system_matrix.to_quaternion()

    total_bone_count = 0
    for armature_object in filter(lambda x: x.data is not None, armature_objects):
        armature_data = typing_cast(Armature, armature_object.data)
        total_bone_count += len(armature_data.bones)

    # Store the bone names to be exported for each armature object.
    armature_object_bone_names: Dict[Object, List[str]] = dict()
    for armature_object in  armature_objects:
        armature_bone_collection_indices: List[int] = []
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
    armature_object_root_bone_indices: Dict[Optional[Object], int] = dict()
    bones: List[Tuple[PsxBone, Optional[Object]]] = []

    if len(armature_objects) == 0 or total_bone_count == 0:
        # If the mesh has no armature object or no bones, simply assign it a dummy bone at the root to satisfy the
        # requirement that a PSK file must have at least one bone.
        psx_bone = PsxBone()
        psx_bone.name = convert_string_to_cp1252_bytes(root_bone_name)
        psx_bone.rotation = convert_bpy_quaternion_to_psx_quaternion(coordinate_system_default_rotation)
        bones.append((psx_bone, None))

        armature_object_root_bone_indices[None] = 0
    else:
        # If we have multiple root armature objects, create a root bone at the world origin.
        if len(armature_tree.root_nodes) > 1:
            psx_bone = PsxBone()
            psx_bone.name = convert_string_to_cp1252_bytes(root_bone_name)
            psx_bone.children_count = total_bone_count
            psx_bone.rotation = convert_bpy_quaternion_to_psx_quaternion(coordinate_system_default_rotation)
            bones.append((psx_bone, None))

            armature_object_root_bone_indices[None] = 0

        root_bone = bones[0][0] if len(bones) > 0 else None

        # TODO: child armatures are not being correctly transformed when parented to a bone.

        # Iterate through all the armature objects.
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

    # Check if any of the armatures are parented to one another.
    # If so, adjust the hierarchy as though they are part of the same armature object.
    # This will let us re-use rig components without destructively joining them.
    for armature_object in armature_objects:
        if armature_object.parent not in armature_objects:
            continue
        # This armature object is parented to another armature object that we are exporting.
        # First fetch the root bone indices for the two armature objects.
        root_bone_index = armature_object_root_bone_indices[armature_object]
        parent_root_bone_index = armature_object_root_bone_indices[armature_object.parent]

        match armature_object.parent_type:
            case 'OBJECT':
                # Parent this armature's root bone to the root bone of the parent object.
                bones[root_bone_index][0].parent_index = parent_root_bone_index
            case 'BONE':
                # Parent this armature's root bone to the specified bone in the parent.
                new_parent_index = None
                for bone_index, (bone, bone_armature_object) in enumerate(bones):
                    if bone.name == convert_string_to_cp1252_bytes(armature_object.parent_bone) and bone_armature_object == armature_object.parent:
                        new_parent_index = bone_index
                        break
                if new_parent_index == None:
                    raise RuntimeError(f'Bone \'{armature_object.parent_bone}\' could not be found in armature \'{armature_object.parent.name}\'.')
                bones[root_bone_index][0].parent_index = new_parent_index
            case _:
                raise RuntimeError(f'Unhandled parent type ({armature_object.parent_type}) for object {armature_object.name}.\n'
                                    f'Parent type must be \'Object\' or \'Bone\'.'
                                    )

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
        self.mesh_dfs_objects: List[DfsObject] = []
        self.armature_objects: List[Object] = []


def get_materials_for_mesh_objects(depsgraph: Depsgraph, mesh_objects: Iterable[Object]):
    yielded_materials = set()
    for mesh_object in mesh_objects:
        evaluated_mesh_object = mesh_object.evaluated_get(depsgraph)
        for i, material_slot in enumerate(evaluated_mesh_object.material_slots):
            material = material_slot.material
            if material is None:
                raise RuntimeError(f'Material slots cannot be empty. ({mesh_object.name}, index {i})')
            if material not in yielded_materials:
                yielded_materials.add(material)
                yield material


def get_mesh_objects_for_collection(collection: Collection) -> Iterable[DfsObject]:
    return filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection))


def get_mesh_objects_for_context(context: Context) -> Iterable[DfsObject]:
    if context.view_layer is None:
        return
    for dfs_object in dfs_view_layer_objects(context.view_layer):
        if dfs_object.obj.type == 'MESH' and dfs_object.is_selected:
            yield dfs_object


def get_armature_for_mesh_object(mesh_object: Object) -> Optional[Object]:
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
        raise RuntimeError('At least one mesh must be selected')
    input_objects = PskInputObjects()
    input_objects.mesh_dfs_objects = mesh_dfs_objects
    # Get the armature objects used on all the meshes being exported.
    armature_objects = get_armatures_for_mesh_objects(map(lambda x: x.obj, mesh_dfs_objects))
    # Sort them in hierarchy order.
    input_objects.armature_objects = list(ObjectTree.from_objects(armature_objects).objects_dfs())
    return input_objects


def get_psk_input_objects_for_context(context: Context) -> PskInputObjects:
    mesh_objects = list(get_mesh_objects_for_context(context))
    return _get_psk_input_objects(mesh_objects)


def get_psk_input_objects_for_collection(collection: Collection) -> PskInputObjects:
    mesh_objects = get_mesh_objects_for_collection(collection)
    return _get_psk_input_objects(mesh_objects)
