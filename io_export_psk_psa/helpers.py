from typing import List


def populate_bone_groups_list(armature_object, bone_group_list):
    bone_group_list.clear()

    item = bone_group_list.add()
    item.name = '(unassigned)'
    item.index = -1
    item.is_selected = True

    for bone_group_index, bone_group in enumerate(armature_object.pose.bone_groups):
        item = bone_group_list.add()
        item.name = bone_group.name
        item.index = bone_group_index
        item.is_selected = True


def add_bone_groups_to_layout(layout):
    pass


def get_export_bone_indices_for_bone_groups(armature_object, bone_group_indices: List[int]) -> List[int]:
    """
    Returns a sorted list of bone indices that should be exported for the given bone groups.

    Note that the ancestors of bones within the bone groups will also be present in the returned list.

    :param armature_object: Blender object with type 'ARMATURE'
    :param bone_group_indices: List of bone group indices to be exported.
    :return: A sorted list of bone indices that should be exported.
    """
    if armature_object is None or armature_object.type != 'ARMATURE':
        raise ValueError('An armature object must be supplied')

    bones = armature_object.data.bones
    pose_bones = armature_object.pose.bones
    bone_names = [x.name for x in bones]

    # Get a list of the bone indices that are explicitly part of the bone groups we are including.
    bone_index_stack = []
    is_exporting_none_bone_groups = -1 in bone_group_indices
    for bone_index, pose_bone in enumerate(pose_bones):
        if (pose_bone.bone_group is None and is_exporting_none_bone_groups) or \
                (pose_bone.bone_group is not None and pose_bone.bone_group_index in bone_group_indices):
            bone_index_stack.append(bone_index)

    # For each bone that is explicitly being added, recursively walk up the hierarchy and ensure that all of
    # those ancestor bone indices are also in the list.
    bone_indices = set()
    while len(bone_index_stack) > 0:
        bone_index = bone_index_stack.pop()
        bone = bones[bone_index]
        if bone.parent is not None:
            parent_bone_index = bone_names.index(bone.parent.name)
            if parent_bone_index not in bone_indices:
                bone_index_stack.append(parent_bone_index)
        bone_indices.add(bone_index)

    return list(sorted(list(bone_indices)))
