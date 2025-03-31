import re
import sys
from fnmatch import fnmatch
from typing import List, Optional
from bpy.props import (
    BoolProperty,
    PointerProperty,
    EnumProperty,
    FloatProperty,
    CollectionProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup, Object, Action, AnimData, Context
from ...shared.types import ForwardUpAxisMixin, ExportSpaceMixin, PsxBoneExportMixin


def psa_export_property_group_animation_data_override_poll(_context, obj):
    return obj.animation_data is not None


class PSA_PG_export_action_list_item(PropertyGroup):
    action: PointerProperty(type=Action)
    name: StringProperty()
    is_selected: BoolProperty(default=True)
    frame_start: IntProperty(options={'HIDDEN'})
    frame_end: IntProperty(options={'HIDDEN'})
    is_pose_marker: BoolProperty(options={'HIDDEN'})


class PSA_PG_export_active_action_list_item(PropertyGroup):
    action: PointerProperty(type=Action)
    name: StringProperty()
    armature_object: PointerProperty(type=Object)
    is_selected: BoolProperty(default=True)
    frame_start: IntProperty(options={'HIDDEN'})
    frame_end: IntProperty(options={'HIDDEN'})


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


def get_sequences_from_name_and_frame_range(name: str, frame_start: int, frame_end: int):
    reversed_pattern = r'(.+)/(.+)'
    reversed_match = re.match(reversed_pattern, name)
    if reversed_match:
        forward_name = reversed_match.group(1)
        backwards_name = reversed_match.group(2)
        yield forward_name, frame_start, frame_end
        yield backwards_name, frame_end, frame_start
    else:
        yield name, frame_start, frame_end


def nla_track_update_cb(self: 'PSA_PG_export', context: Context) -> None:
    self.nla_strip_list.clear()
    match = re.match(r'^(\d+).+$', self.nla_track)
    self.nla_track_index = int(match.group(1)) if match else -1
    if self.nla_track_index >= 0:
        animation_data = get_animation_data(self, context)
        if animation_data is None:
            return
        nla_track = animation_data.nla_tracks[self.nla_track_index]
        for nla_strip in nla_track.strips:
            for sequence_name, frame_start, frame_end in get_sequences_from_name_and_frame_range(nla_strip.name, nla_strip.frame_start, nla_strip.frame_end):
                strip: PSA_PG_export_nla_strip_list_item = self.nla_strip_list.add()
                strip.action = nla_strip.action
                strip.name = sequence_name
                strip.frame_start = frame_start
                strip.frame_end = frame_end


def get_animation_data(pg: 'PSA_PG_export', context: Context) -> Optional[AnimData]:
    animation_data_object = context.object
    if pg.should_override_animation_data:
        animation_data_object = pg.animation_data_override
    return animation_data_object.animation_data if animation_data_object else None


def nla_track_search_cb(self, context: Context, edit_text: str):
    pg = getattr(context.scene, 'psa_export')
    animation_data = get_animation_data(pg, context)
    if animation_data is not None:
        for index, nla_track in enumerate(animation_data.nla_tracks):
            yield f'{index} - {nla_track.name}'


def animation_data_override_update_cb(self: 'PSA_PG_export', context: Context):
    # Reset NLA track selection
    self.nla_track = ''


class PSA_PG_export(PropertyGroup, ForwardUpAxisMixin, ExportSpaceMixin, PsxBoneExportMixin):
    should_override_animation_data: BoolProperty(
        name='Override Animation Data',
        options=set(),
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
        options=set(),
        description='',
        items=(
            ('ACTIONS', 'Actions', 'Sequences will be exported using actions', 'ACTION', 0),
            ('TIMELINE_MARKERS', 'Timeline Markers', 'Sequences are delineated by scene timeline markers', 'MARKER_HLT', 1),
            ('NLA_TRACK_STRIPS', 'NLA Track Strips', 'Sequences are delineated by the start & end times of strips on the selected NLA track', 'NLA', 2),
            ('ACTIVE_ACTION', 'Active Action', 'The active action will be exported for each selected armature', 'ACTION', 3),
        )
    )
    nla_track: StringProperty(
        name='NLA Track',
        options=set(),
        description='',
        search=nla_track_search_cb,
        update=nla_track_update_cb
    )
    nla_track_index: IntProperty(name='NLA Track Index', default=-1)
    fps_source: EnumProperty(
        name='FPS Source',
        options=set(),
        description='',
        items=(
            ('SCENE', 'Scene', '', 'SCENE_DATA', 0),
            ('ACTION_METADATA', 'Action Metadata', 'The frame rate will be determined by action\'s FPS property found in the PSA Export panel.\n\nIf the Sequence Source is Timeline Markers, the lowest value of all contributing actions will be used', 'ACTION', 1),
            ('CUSTOM', 'Custom', '', 2)
        )
    )
    fps_custom: FloatProperty(default=30.0, min=sys.float_info.epsilon, soft_min=1.0, options=set(), step=100,
                              soft_max=60.0)
    compression_ratio_source: EnumProperty(
        name='Compression Ratio Source',
        options=set(),
        description='',
        items=(
            ('ACTION_METADATA', 'Action Metadata', 'The compression ratio will be determined by action\'s Compression Ratio property found in the PSA Export panel.\n\nIf the Sequence Source is Timeline Markers, the lowest value of all contributing actions will be used', 'ACTION', 1),
            ('CUSTOM', 'Custom', '', 2)
        )
    )
    compression_ratio_custom: FloatProperty(default=1.0, min=0.0, max=1.0, subtype='FACTOR', description='The key sampling ratio of the exported sequence.\n\nA compression ratio of 1.0 will export all frames, while a compression ratio of 0.5 will export half of the frames')
    action_list: CollectionProperty(type=PSA_PG_export_action_list_item)
    action_list_index: IntProperty(default=0)
    marker_list: CollectionProperty(type=PSA_PG_export_timeline_markers)
    marker_list_index: IntProperty(default=0)
    nla_strip_list: CollectionProperty(type=PSA_PG_export_nla_strip_list_item)
    nla_strip_list_index: IntProperty(default=0)
    active_action_list: CollectionProperty(type=PSA_PG_export_active_action_list_item)
    active_action_list_index: IntProperty(default=0)
    sequence_name_prefix: StringProperty(name='Prefix', options=set())
    sequence_name_suffix: StringProperty(name='Suffix', options=set())
    sequence_filter_name: StringProperty(
        default='',
        name='Filter by Name',
        options={'TEXTEDIT_UPDATE'},
        description='Only show items matching this name (use \'*\' as wildcard)')
    sequence_use_filter_invert: BoolProperty(
        default=False,
        name='Invert',
        options=set(),
        description='Invert filtering (show hidden items, and vice versa)')
    sequence_filter_asset: BoolProperty(
        default=False,
        name='Show assets',
        options=set(),
        description='Show actions that belong to an asset library')
    sequence_filter_pose_marker: BoolProperty(
        default=True,
        name='Show pose markers',
        options=set())
    sequence_use_filter_sort_reverse: BoolProperty(default=True, options=set())
    sequence_filter_reversed: BoolProperty(
        default=True,
        options=set(),
        name='Show Reversed',
        description='Show reversed sequences'
    )
    scale: FloatProperty(
        name='Scale',
        default=1.0,
        description='Scale factor to apply to the bone translations. Use this if you are exporting animations for a scaled PSK mesh',
        min=0.0,
        soft_max=100.0
    )
    sampling_mode: EnumProperty(
        name='Sampling Mode',
        options=set(),
        description='The method by which frames are sampled',
        items=(
            ('INTERPOLATED', 'Interpolated', 'Sampling is performed by interpolating the evaluated bone poses from the adjacent whole frames.', 'INTERPOLATED', 0),
            ('SUBFRAME', 'Subframe', 'Sampling is performed by evaluating the bone poses at the subframe time.\n\nNot recommended unless you are also animating with subframes enabled.', 'SUBFRAME', 1),
        ),
        default='INTERPOLATED'
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
    PSA_PG_export_active_action_list_item,
    PSA_PG_export,
)
