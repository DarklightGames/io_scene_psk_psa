from bpy.types import NlaStrip
from typing import List
from collections import Counter


def rgb_to_srgb(c):
    if c > 0.0031308:
        return 1.055 * (pow(c, (1.0 / 2.4))) - 0.055
    else:
        return 12.92 * c


def get_nla_strips_ending_at_frame(object, frame) -> List[NlaStrip]:
    if object is None or object.animation_data is None:
        return []
    strips = []
    for nla_track in object.animation_data.nla_tracks:
        for strip in nla_track.strips:
            if strip.frame_end == frame:
                strips.append(strip)
    return strips


def get_nla_strips_in_timeframe(object, frame_min, frame_max) -> List[NlaStrip]:
    if object is None or object.animation_data is None:
        return []
    strips = []
    for nla_track in object.animation_data.nla_tracks:
        for strip in nla_track.strips:
            if strip.frame_end >= frame_min and strip.frame_start <= frame_max:
                strips.append(strip)
    return strips


def populate_bone_group_list(armature_object, bone_group_list):
    bone_group_list.clear()

    if armature_object and armature_object.pose:
        bone_group_counts = Counter(map(lambda x: x.bone_group, armature_object.pose.bones))

        item = bone_group_list.add()
        item.name = 'Unassigned'
        item.index = -1
        item.count = 0 if None not in bone_group_counts else bone_group_counts[None]
        item.is_selected = True

        for bone_group_index, bone_group in enumerate(armature_object.pose.bone_groups):
            item = bone_group_list.add()
            item.name = bone_group.name
            item.index = bone_group_index
            item.count = 0 if bone_group not in bone_group_counts else bone_group_counts[bone_group]
            item.is_selected = True


def get_psa_sequence_name(action, should_use_original_sequence_name):
    if should_use_original_sequence_name and 'original_sequence_name' in action:
        return action['original_sequence_name']
    else:
        return action.name


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
