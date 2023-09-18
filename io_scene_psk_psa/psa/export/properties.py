import re
import sys
from fnmatch import fnmatch
from typing import List, Optional

from bpy.props import BoolProperty, PointerProperty, EnumProperty, FloatProperty, CollectionProperty, IntProperty, \
    StringProperty
from bpy.types import PropertyGroup, Object, Action, AnimData, Context

from ...types import PSX_PG_bone_collection_list_item


def psa_export_property_group_animation_data_override_poll(_context, obj):
    return obj.animation_data is not None


empty_set = set()


class PSA_PG_export_action_list_item(PropertyGroup):
    action: PointerProperty(type=Action)
    name: StringProperty()
    is_selected: BoolProperty(default=False)
    frame_start: IntProperty(options={'HIDDEN'})
    frame_end: IntProperty(options={'HIDDEN'})
    is_pose_marker: BoolProperty(options={'HIDDEN'})


class PSA_PG_export_timeline_markers(PropertyGroup):  # TODO: rename this to singular
    marker_index: IntProperty()
    name: StringProperty()
    is_selected: BoolProperty(default=True)
    frame_start: IntProperty(options={'HIDDEN'})
    frame_end: IntProperty(options={'HIDDEN'})


class PSA_PG_export_nla_strip_list_item(PropertyGroup):
    name: StringProperty()
    action: PointerProperty(type=Action)
    frame_start: FloatProperty()
    frame_end: FloatProperty()
    is_selected: BoolProperty(default=True)


def nla_track_update_cb(self: 'PSA_PG_export', context: Context) -> None:
    self.nla_strip_list.clear()
    if context.object is None or context.object.animation_data is None:
        return
    match = re.match(r'^(\d+).+$', self.nla_track)
    self.nla_track_index = int(match.group(1)) if match else -1
    if self.nla_track_index >= 0:
        nla_track = context.object.animation_data.nla_tracks[self.nla_track_index]
        for nla_strip in nla_track.strips:
            strip: PSA_PG_export_nla_strip_list_item = self.nla_strip_list.add()
            strip.action = nla_strip.action
            strip.name = nla_strip.name
            strip.frame_start = nla_strip.frame_start
            strip.frame_end = nla_strip.frame_end


def get_animation_data(pg: 'PSA_PG_export', context: Context) -> Optional[AnimData]:
    animation_data_object = context.object
    if pg.should_override_animation_data:
        animation_data_object = pg.animation_data_override
    return animation_data_object.animation_data if animation_data_object else None


def nla_track_search_cb(self, context: Context, edit_text: str):
    pg = getattr(context.scene, 'psa_export')
    animation_data = get_animation_data(pg, context)
    if animation_data is None:
        return
    for index, nla_track in enumerate(animation_data.nla_tracks):
        yield f'{index} - {nla_track.name}'


def animation_data_override_update_cb(self: 'PSA_PG_export', context: Context):
    # Reset NLA track selection
    self.nla_track = ''


class PSA_PG_export(PropertyGroup):
    root_motion: BoolProperty(
        name='Root Motion',
        options=empty_set,
        default=False,
        description='When enabled, the root bone will be transformed as it appears in the scene.\n\n'
                    'You might want to disable this if you are exporting an animation for an armature that is '
                    'attached to another object, such as a weapon or a shield',
    )
    should_override_animation_data: BoolProperty(
        name='Override Animation Data',
        options=empty_set,
        default=False,
        description='Use the animation data from a different object instead of the selected object',
        update=animation_data_override_update_cb,
    )
    animation_data_override: PointerProperty(
        type=Object,
        update=animation_data_override_update_cb,
        poll=psa_export_property_group_animation_data_override_poll
    )
    sequence_source: EnumProperty(
        name='Source',
        options=empty_set,
        description='',
        items=(
            ('ACTIONS', 'Actions', 'Sequences will be exported using actions', 'ACTION', 0),
            ('TIMELINE_MARKERS', 'Timeline Markers', 'Sequences are delineated by scene timeline markers', 'MARKER_HLT', 1),
            ('NLA_TRACK_STRIPS', 'NLA Track Strips', 'Sequences are delineated by the start & end times of strips on the selected NLA track', 'NLA', 2)
        )
    )
    nla_track: StringProperty(
        name='NLA Track',
        options=empty_set,
        description='',
        search=nla_track_search_cb,
        update=nla_track_update_cb
    )
    nla_track_index: IntProperty(name='NLA Track Index', default=-1)
    fps_source: EnumProperty(
        name='FPS Source',
        options=empty_set,
        description='',
        items=(
            ('SCENE', 'Scene', '', 'SCENE_DATA', 0),
            ('ACTION_METADATA', 'Action Metadata',
             'The frame rate will be determined by action\'s "psa_sequence_fps" custom property, if it exists. If the Sequence Source is Timeline Markers, the lowest value of all contributing actions will be used. If no metadata is available, the scene\'s frame rate will be used.',
             'PROPERTIES', 1),
            ('CUSTOM', 'Custom', '', 2)
        )
    )
    fps_custom: FloatProperty(default=30.0, min=sys.float_info.epsilon, soft_min=1.0, options=empty_set, step=100,
                              soft_max=60.0)
    action_list: CollectionProperty(type=PSA_PG_export_action_list_item)
    action_list_index: IntProperty(default=0)
    marker_list: CollectionProperty(type=PSA_PG_export_timeline_markers)
    marker_list_index: IntProperty(default=0)
    nla_strip_list: CollectionProperty(type=PSA_PG_export_nla_strip_list_item)
    nla_strip_list_index: IntProperty(default=0)
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        options=empty_set,
        description='',
        items=(
            ('ALL', 'All', 'All bones will be exported.'),
            ('BONE_COLLECTIONS', 'Bone Collections', 'Only bones belonging to the selected bone collections and their '
             'ancestors will be exported.'),
        )
    )
    bone_collection_list: CollectionProperty(type=PSX_PG_bone_collection_list_item)
    bone_collection_list_index: IntProperty(default=0, name='', description='')
    should_enforce_bone_name_restrictions: BoolProperty(
        default=False,
        name='Enforce Bone Name Restrictions',
        description='Bone names restrictions will be enforced. Note that bone names without properly formatted names '
                    'cannot be referenced in scripts'
    )
    sequence_name_prefix: StringProperty(name='Prefix', options=empty_set)
    sequence_name_suffix: StringProperty(name='Suffix', options=empty_set)
    sequence_filter_name: StringProperty(
        default='',
        name='Filter by Name',
        options={'TEXTEDIT_UPDATE'},
        description='Only show items matching this name (use \'*\' as wildcard)')
    sequence_use_filter_invert: BoolProperty(
        default=False,
        name='Invert',
        options=empty_set,
        description='Invert filtering (show hidden items, and vice versa)')
    sequence_filter_asset: BoolProperty(
        default=False,
        name='Show assets',
        options=empty_set,
        description='Show actions that belong to an asset library')
    sequence_filter_pose_marker: BoolProperty(
        default=True,
        name='Show pose markers',
        options=empty_set)
    sequence_use_filter_sort_reverse: BoolProperty(default=True, options=empty_set)
    sequence_filter_reversed: BoolProperty(
        default=True,
        options=empty_set,
        name='Show Reversed',
        description='Show reversed sequences'
    )


def filter_sequences(pg: PSA_PG_export, sequences) -> List[int]:
    bitflag_filter_item = 1 << 30
    flt_flags = [bitflag_filter_item] * len(sequences)

    if pg.sequence_filter_name:
        # Filter name is non-empty.
        for i, sequence in enumerate(sequences):
            if not fnmatch(sequence.name, f'*{pg.sequence_filter_name}*'):
                flt_flags[i] &= ~bitflag_filter_item

        # Invert filter flags for all items.
        if pg.sequence_use_filter_invert:
            for i, sequence in enumerate(sequences):
                flt_flags[i] ^= bitflag_filter_item

    if not pg.sequence_filter_asset:
        for i, sequence in enumerate(sequences):
            if hasattr(sequence, 'action') and sequence.action is not None and sequence.action.asset_data is not None:
                flt_flags[i] &= ~bitflag_filter_item

    if not pg.sequence_filter_pose_marker:
        for i, sequence in enumerate(sequences):
            if hasattr(sequence, 'is_pose_marker') and sequence.is_pose_marker:
                flt_flags[i] &= ~bitflag_filter_item

    if not pg.sequence_filter_reversed:
        for i, sequence in enumerate(sequences):
            if sequence.frame_start > sequence.frame_end:
                flt_flags[i] &= ~bitflag_filter_item

    return flt_flags


classes = (
    PSA_PG_export_action_list_item,
    PSA_PG_export_timeline_markers,
    PSA_PG_export_nla_strip_list_item,
    PSA_PG_export,
)
