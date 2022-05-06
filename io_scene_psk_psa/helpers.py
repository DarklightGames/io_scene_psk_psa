import datetime
from collections import Counter
from typing import List, Iterable

from bpy.types import NlaStrip, Object
from .types import BoneGroupListItem


class Timer:
    def __enter__(self):
        self.start = datetime.datetime.now()
        self.interval = None
        return self

    def __exit__(self, *args):
        self.end = datetime.datetime.now()
        self.interval = self.end - self.start

    @property
    def duration(self):
        if self.interval is not None:
            return self.interval
        else:
            return datetime.datetime.now() - self.start


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
        if nla_track.mute:
            continue
        for strip in nla_track.strips:
            if (strip.frame_start < frame_min and strip.frame_end > frame_max) or \
                    (frame_min <= strip.frame_start < frame_max) or \
                    (frame_min < strip.frame_end <= frame_max):
                strips.append(strip)
    return strips


def populate_bone_group_list(armature_object: Object, bone_group_list: Iterable[BoneGroupListItem]) -> None:
    """
    Updates the bone group collection.

    Bone group selections are preserved between updates unless none of the groups were previously selected;
    otherwise, all groups are selected by default.
    """
    has_selected_groups = any([g.is_selected for g in bone_group_list])
    unassigned_group_is_selected, selected_assigned_group_names = True, []

    if has_selected_groups:
        # Preserve group selections before clearing the list.
        # We handle selections for the unassigned group separately to cover the edge case
        # where there might be an actual group with 'Unassigned' as its name.
        unassigned_group_idx, unassigned_group_is_selected = next(iter([
            (i, g.is_selected) for i, g in enumerate(bone_group_list) if g.index == -1]), (-1, False))

        selected_assigned_group_names = [
            g.name for i, g in enumerate(bone_group_list) if i != unassigned_group_idx and g.is_selected]

    bone_group_list.clear()

    if armature_object and armature_object.pose:
        bone_group_counts = Counter(map(lambda x: x.bone_group, armature_object.pose.bones))

        item = bone_group_list.add()
        item.name = 'Unassigned'
        item.index = -1
        item.count = 0 if None not in bone_group_counts else bone_group_counts[None]
        item.is_selected = unassigned_group_is_selected

        for bone_group_index, bone_group in enumerate(armature_object.pose.bone_groups):
            item = bone_group_list.add()
            item.name = bone_group.name
            item.index = bone_group_index
            item.count = 0 if bone_group not in bone_group_counts else bone_group_counts[bone_group]
            item.is_selected = bone_group.name in selected_assigned_group_names if has_selected_groups else True


def get_psa_sequence_name(action, should_use_original_sequence_name):
    if should_use_original_sequence_name and 'psa_sequence_name' in action:
        return action['psa_sequence_name']
    else:
        return action.name


def get_export_bone_names(armature_object, bone_filter_mode, bone_group_indices: List[int]) -> List[str]:
    """
    Returns a sorted list of bone indices that should be exported for the given bone filter mode and bone groups.

    Note that the ancestors of bones within the bone groups will also be present in the returned list.

    :param armature_object: Blender object with type 'ARMATURE'
    :param bone_filter_mode: One of ['ALL', 'BONE_GROUPS']
    :param bone_group_indices: List of bone group indices to be exported.
    :return: A sorted list of bone indices that should be exported.
    """
    if armature_object is None or armature_object.type != 'ARMATURE':
        raise ValueError('An armature object must be supplied')

    bones = armature_object.data.bones
    pose_bones = armature_object.pose.bones
    bone_names = [x.name for x in bones]

    # Get a list of the bone indices that we are explicitly including.
    bone_index_stack = []
    is_exporting_none_bone_groups = -1 in bone_group_indices
    for bone_index, pose_bone in enumerate(pose_bones):
        if bone_filter_mode == 'ALL' or \
                (pose_bone.bone_group is None and is_exporting_none_bone_groups) or \
                (pose_bone.bone_group is not None and pose_bone.bone_group_index in bone_group_indices):
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
    # For example, users of this function may modify bone lists, which would invalidate the indices and require a
    # index mapping scheme to resolve it. Using strings is more comfy and results in less code downstream.
    instigator_bone_names = [bones[x[1]].name if x[1] is not None else None for x in bone_indices]
    bone_names = [bones[x[0]].name for x in bone_indices]

    # Ensure that the hierarchy we are sending back has a single root bone.
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
