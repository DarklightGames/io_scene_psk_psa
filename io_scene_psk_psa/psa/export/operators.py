from abc import abstractmethod
from collections import Counter
from typing import List, Iterable, Dict, Protocol, Sequence, Tuple, cast as typing_cast

import bpy
import re
from bpy.props import StringProperty
from bpy.types import Context, Action, Object, AnimData, TimelineMarker, Operator, Armature, UILayout, Scene
from bpy_extras.io_utils import ExportHelper

from .properties import (
    PSA_PG_export,
    PSA_PG_export_action_list_item,
    PsaExportMixin,
    PsaExportSequenceMixin,
    PsaExportSequenceWithActionMixin,
    filter_sequences,
    get_sequences_from_name_and_frame_range,
)
from .ui import PSA_UL_export_sequences
from ..builder import build_psa, PsaBuildSequence, PsaBuildOptions
from psk_psa_py.psa.writer import write_psa_to_file
from ...shared.helpers import get_collection_export_operator_from_context, get_collection_from_context, get_psk_input_objects_for_collection, populate_bone_collection_list, get_nla_strips_in_frame_range, PsxBoneCollection
from ...shared.types import BpyCollectionProperty, PSX_PG_action_export
from ...shared.ui import draw_bone_filter_mode
from ...shared.operators import PSK_OT_bone_collection_list_populate, PSK_OT_bone_collection_list_select_all


def get_sequences_propnames_from_source(sequence_source: str) -> Tuple[str, str]:
    match sequence_source:
        case 'ACTIONS':
            return 'action_list', 'action_list_index'
        case 'TIMELINE_MARKERS':
            return 'marker_list', 'marker_list_index'
        case 'NLA_TRACK_STRIPS':
            return 'nla_strip_list', 'nla_strip_list_index'
        case 'ACTIVE_ACTION':
            return 'active_action_list', 'active_action_list_index'
        case _:
            assert False, f'Invalid sequence source: {sequence_source}'


def is_action_for_object(obj: Object, action: Action):
    if len(action.layers) == 0:
        return False

    if obj is None or obj.animation_data is None or obj.type != 'ARMATURE':
        return False

    armature_data = typing_cast(Armature, obj.data)
    bone_names = set([x.name for x in armature_data.bones])

    # The nesting here is absolutely bonkers.
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                for fcurve in channelbag.fcurves:
                    match = re.match(r'pose\.bones\[\"([^\"]+)\"](\[\"([^\"]+)\"])?', fcurve.data_path)
                    if not match:
                        continue
                    bone_name = match.group(1)
                    if bone_name in bone_names:
                        return True
    
    return False


def update_actions_and_timeline_markers(context: Context, armature_objects: Sequence[Object], pg: PsaExportMixin):
    assert context.scene is not None

    # Clear actions and markers.
    pg.action_list.clear()
    pg.marker_list.clear()
    pg.active_action_list.clear()

    # TODO: this is cleared in the callback, although this should probably be changed.
    # pg.nla_strip_list.clear()
    
    assert len(armature_objects) >= 0, 'Must have at least one armature object'

    # TODO: for now, use the first armature object's animation data.
    # animation_data_object = get_animation_data_object(context, pg)
    armature_object = armature_objects[0]
    animation_data = armature_object.animation_data if armature_object else None

    if animation_data is None:
        return

    # Populate actions list.
    for action in bpy.data.actions:
        if not any(map(lambda armature_object: is_action_for_object(armature_object, action), armature_objects)):
            # This action is not applicable to any of the selected armatures.
            continue

        for (name, frame_start, frame_end) in get_sequences_from_action(action):
            item = pg.action_list.add()
            item.action_name = action.name
            item.name = name
            item.is_selected = False
            item.is_pose_marker = False
            item.frame_start = frame_start
            item.frame_end = frame_end

        # Pose markers are not guaranteed to be in frame-order, so make sure that they are.
        pose_markers = sorted(action.pose_markers, key=lambda x: x.frame)
        for pose_marker_index, pose_marker in enumerate(pose_markers):
            sequences = get_sequences_from_action_pose_markers(action, pose_markers, pose_marker, pose_marker_index)
            for (name, frame_start, frame_end) in sequences:
                item = pg.action_list.add()
                item.action_name = action.name
                item.name = name
                item.is_selected = False
                item.is_pose_marker = True
                item.frame_start = frame_start
                item.frame_end = frame_end

    # Populate timeline markers list.
    marker_names = [x.name for x in context.scene.timeline_markers]
    sequence_frame_ranges = get_timeline_marker_sequence_frame_ranges(animation_data, context.scene, marker_names)

    for marker_name in marker_names:
        if marker_name not in sequence_frame_ranges:
            continue
        if marker_name.strip() == '' or marker_name.startswith('#'):
            continue
        frame_start, frame_end = sequence_frame_ranges[marker_name]
        sequences = get_sequences_from_name_and_frame_range(marker_name, frame_start, frame_end)
        for (sequence_name, frame_start, frame_end) in sequences:
            item = pg.marker_list.add()
            item.name = sequence_name
            item.is_selected = False
            item.frame_start = frame_start
            item.frame_end = frame_end

    # Populate the active action list.
    for armature_object in armature_objects:
        active_action = armature_object.animation_data.action if armature_object.animation_data else None
        if active_action is None:
            continue
        sequences = get_sequences_from_action(active_action)
        for (sequence_name, frame_start, frame_end) in sequences:
            # TODO: for some reason we aren't doing the sequence name parsing here.
            item = pg.active_action_list.add()
            item.name = sequence_name
            item.armature_object_name = armature_object.name
            item.action_name = active_action.name
            item.frame_start = frame_start
            item.frame_end = frame_end
            item.is_selected = True


def get_sequence_fps(context: Context, fps_source: str, fps_custom: float, actions: Iterable[Action]) -> float:
    match fps_source:
        case 'SCENE':
            assert context.scene
            return context.scene.render.fps
        case 'CUSTOM':
            return fps_custom
        case 'ACTION_METADATA':
            # Get the minimum value of action metadata FPS values.
            return min([typing_cast(PSX_PG_action_export, getattr(action, 'psa_export')).fps for action in actions])
        case _:
            assert False, f'Invalid FPS source: {fps_source}'


def get_sequence_compression_ratio(
        compression_ratio_source: str, 
        compression_ratio_custom: float, 
        actions: Iterable[Action],
        ) -> float:
    match compression_ratio_source:
        case 'ACTION_METADATA':
            # Get the minimum value of action metadata compression ratio values.
            return min(map(lambda action: typing_cast(PSX_PG_action_export, getattr(action, 'psa_export')).compression_ratio, actions))
        case 'CUSTOM':
            return compression_ratio_custom
        case _:
            assert False, f'Invalid compression ratio source: {compression_ratio_source}'


def get_timeline_marker_sequence_frame_ranges(
        animation_data: AnimData, 
        scene: Scene,
        marker_names: List[str],
        ) -> dict[str, tuple[int, int]]:
    # Timeline markers need to be sorted so that we can determine the sequence start and end positions.
    sequence_frame_ranges: dict[str, tuple[int, int]] = dict()
    sorted_timeline_markers = list(sorted(scene.timeline_markers, key=lambda x: x.frame))
    sorted_timeline_marker_names = [x.name for x in sorted_timeline_markers]

    for marker_name in marker_names:
        marker = scene.timeline_markers[marker_name]
        frame_start = marker.frame
        # Determine the final frame of the sequence based on the next marker.
        # If no subsequent marker exists, use the maximum frame_end from all NLA strips.
        marker_index = sorted_timeline_marker_names.index(marker_name)
        next_marker_index = marker_index + 1
        frame_end = 0
        if next_marker_index < len(sorted_timeline_markers):
            # There is a next marker. Use that next marker's frame position as the last frame of this sequence.
            frame_end = sorted_timeline_markers[next_marker_index].frame
            nla_strips = list(get_nla_strips_in_frame_range(animation_data, marker.frame, frame_end))
            if len(nla_strips) > 0:
                frame_end = min(frame_end, max(map(lambda nla_strip: nla_strip.frame_end, nla_strips)))
                frame_start = max(frame_start, min(map(lambda nla_strip: nla_strip.frame_start, nla_strips)))
            else:
                # No strips in between this marker and the next, just export this as a one-frame animation.
                frame_end = frame_start
        else:
            # There is no next marker.
            # Find the final frame of all the NLA strips and use that as the last frame of this sequence.
            for nla_track in animation_data.nla_tracks:
                if nla_track.mute:
                    continue
                for strip in nla_track.strips:
                    frame_end = max(frame_end, strip.frame_end)

        if frame_start > frame_end:
            continue

        sequence_frame_ranges[marker_name] = int(frame_start), int(frame_end)

    return sequence_frame_ranges


def get_sequences_from_action(action: Action):
    if action.name == '' or action.name.startswith('#'):
        return

    frame_start = int(action.frame_range[0])
    action_name = action.name

    if action_name.startswith('!'):
        # If the pose marker name starts with an exclamation mark, only export the first frame.
        frame_end = frame_start
        action_name = action_name[1:]
    else:
        frame_end = int(action.frame_range[1])

    yield from get_sequences_from_name_and_frame_range(action_name, frame_start, frame_end)


def get_sequences_from_action_pose_markers(
        action: Action, 
        pose_markers: List[TimelineMarker], 
        pose_marker: TimelineMarker, 
        pose_marker_index: int,
        ):
    frame_start = pose_marker.frame
    sequence_name = pose_marker.name
    if pose_marker.name.strip() == '' or pose_marker.name.startswith('#'):
        return
    if pose_marker.name.startswith('!'):
        # If the pose marker name starts with an exclamation mark, only export the first frame.
        frame_end = frame_start
        sequence_name = sequence_name[1:]
    elif pose_marker_index + 1 < len(pose_markers):
        frame_end = pose_markers[pose_marker_index + 1].frame
    else:
        frame_end = int(action.frame_range[1])
    yield from get_sequences_from_name_and_frame_range(sequence_name, frame_start, frame_end)


def get_visible_sequences(pg: PsaExportMixin, sequences) -> List[PSA_PG_export_action_list_item]:
    visible_sequences = []
    for i, flag in enumerate(filter_sequences(pg, sequences)):
        if bool(flag & (1 << 30)):
            visible_sequences.append(sequences[i])
    return visible_sequences



class PSA_OT_export_collection(Operator, ExportHelper, PsaExportMixin):
    bl_idname = 'psa.export_collection'
    bl_label = 'Export'
    bl_options = {'INTERNAL'}
    bl_description = 'Export actions to PSA'
    filename_ext = '.psa'
    filter_glob: StringProperty(default='*.psa', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSA file',
        maxlen=1024,
        default='')

    def execute(self, context: Context):
        # TODO: get the armature objects from the collection export operator
        collection = get_collection_from_context(context)
        if collection is None:
            self.report({'ERROR'}, 'No collection found for export')
            return {'CANCELLED'}
        import_objects = get_psk_input_objects_for_collection(collection)

        options = create_psa_export_options(context, import_objects.armature_objects, self)

        if len(options.sequences) == 0:
            self.report({'ERROR'}, 'No sequences were selected for export')
            return {'CANCELLED'}

        try:
            psa = build_psa(context, options)
            self.report({'INFO'}, f'PSA export successful')
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        write_psa_to_file(psa, self.filepath)

        return {'FINISHED'}

    def draw(self, context: Context):
        layout = self.layout

        assert layout is not None

        flow = layout.grid_flow(row_major=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        # Sequences
        draw_sequences_panel(layout, self,
                             PSA_OT_export_collection_sequences_select_all.bl_idname,
                             PSA_OT_export_collection_sequences_deselect_all.bl_idname,
                             )

        # Bones
        bones_header, bones_panel = layout.panel('Bones', default_closed=False)
        bones_header.label(text='Bones', icon='BONE_DATA')
        if bones_panel:
            draw_bone_filter_mode(bones_panel, self, True)

            if self.bone_filter_mode == 'BONE_COLLECTIONS':
                row = bones_panel.row()
                rows = max(3, min(len(self.bone_collection_list), 10))
                row.template_list('PSX_UL_bone_collection_list', '', self, 'bone_collection_list', self, 'bone_collection_list_index', rows=rows)
                col = row.column(align=True)
                col.operator(PSK_OT_bone_collection_list_populate.bl_idname, text='', icon='FILE_REFRESH')
                col.separator()
                op = col.operator(PSK_OT_bone_collection_list_select_all.bl_idname, text='', icon='CHECKBOX_HLT')
                op.is_selected = True
                op = col.operator(PSK_OT_bone_collection_list_select_all.bl_idname, text='', icon='CHECKBOX_DEHLT')
                op.is_selected = False

            advanced_bones_header, advanced_bones_panel = bones_panel.panel('Advanced', default_closed=True)
            advanced_bones_header.label(text='Advanced')
            if advanced_bones_panel:
                flow = advanced_bones_panel.grid_flow(row_major=True)
                flow.use_property_split = True
                flow.use_property_decorate = False
                flow.prop(self, 'root_bone_name')

        # Transform
        transform_header, transform_panel = layout.panel('Transform', default_closed=False)
        transform_header.label(text='Transform', icon='DRIVER_TRANSFORM')
        if transform_panel:
            flow = transform_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(self, 'export_space')
            flow.prop(self, 'transform_source')

            flow = transform_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False

            match self.transform_source:
                case 'SCENE':
                    transform_source = getattr(context.scene, 'psx_export')
                    flow.enabled = False
                case 'CUSTOM':
                    transform_source = self
                case _:
                    assert False, f'Invalid transform source: {self.transform_source}'
        
            flow.prop(transform_source, 'scale')
            flow.prop(transform_source, 'forward_axis')
            flow.prop(transform_source, 'up_axis')


def draw_sequences_panel(
        layout: UILayout, 
        pg: PsaExportMixin,
        sequences_select_all_operator_idname: str,
        sequences_deselect_all_operator_idname: str,
        ):
    sequences_header, sequences_panel = layout.panel('Sequences', default_closed=False)
    sequences_header.label(text='Sequences', icon='ACTION')

    if sequences_panel:
        sequences_panel.operator(PSA_OT_export_collection_populate_sequences.bl_idname, text='Refresh', icon='FILE_REFRESH')

        flow = sequences_panel.grid_flow()
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(pg, 'sequence_source', text='Source')

        if pg.sequence_source == 'NLA_TRACK_STRIPS':
            flow = sequences_panel.grid_flow()
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'nla_track')

        # SELECT ALL/NONE
        row = sequences_panel.row(align=True)
        row.label(text='Select')
        row.operator(sequences_select_all_operator_idname, text='All', icon='CHECKBOX_HLT')
        row.operator(sequences_deselect_all_operator_idname, text='None', icon='CHECKBOX_DEHLT')

        propname, active_propname = get_sequences_propnames_from_source(pg.sequence_source)
        sequences_panel.template_list(PSA_UL_export_sequences.bl_idname, '', pg, propname, pg, active_propname,
                                        rows=max(3, min(len(getattr(pg, propname)), 10)))

        name_header, name_panel = sequences_panel.panel('Name', default_closed=False)
        name_header.label(text='Name')
        if name_panel:
            flow = name_panel.grid_flow()
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'sequence_name_prefix', text='Name Prefix')
            flow.prop(pg, 'sequence_name_suffix')

            # Determine if there is going to be a naming conflict and display an error, if so.
            selected_items = [x for x in pg.action_list if x.is_selected]
            action_names = [x.name for x in selected_items]
            action_name_counts = Counter(action_names)
            for action_name, count in action_name_counts.items():
                if count > 1:
                    layout.label(text=f'Duplicate action: {action_name}', icon='ERROR')
                    break
    
        # Group
        group_header, group_panel = sequences_panel.panel('Group', default_closed=True)
        group_header.label(text='Group')
        if group_panel is not None:
            group_flow = group_panel.grid_flow()
            group_flow.use_property_split = True
            group_flow.use_property_decorate = False
            group_flow.prop(pg, 'group_source')
            if pg.group_source == 'CUSTOM':
                group_flow.prop(pg, 'group_custom', placeholder='Group')

        # Sampling
        sampling_header, sampling_panel = sequences_panel.panel('Data Source', default_closed=False)
        sampling_header.label(text='Sampling')
        if sampling_panel:
            flow = sampling_panel.grid_flow()
            flow.use_property_split = True
            flow.use_property_decorate = False

            # SAMPLING MODE
            flow.prop(pg, 'sampling_mode', text='Sampling Mode')

            # FPS
            col = flow.row(align=True)
            col.prop(pg, 'fps_source', text='FPS')
            if pg.fps_source == 'CUSTOM':
                col.prop(pg, 'fps_custom', text='')

            # COMPRESSION RATIO
            col = flow.row(align=True)
            col.prop(pg, 'compression_ratio_source', text='Compression Ratio')
            if pg.compression_ratio_source == 'CUSTOM':
                col.prop(pg, 'compression_ratio_custom', text='')


def create_psa_export_options(context: Context, armature_objects: Sequence[Object], pg: PsaExportMixin) -> PsaBuildOptions:
    if len(armature_objects) == 0:
        raise RuntimeError(f'No armatures')

    animation_data = armature_objects[0].animation_data
    export_sequences: List[PsaBuildSequence] = []

    # TODO: this needs to be changed so that we iterate over all of the armature objects?
    # do we need to check for primary key? (data vs. object?)

    def get_export_sequence_group(group_source: str, group_custom: str | None, action: Action | None) -> str | None:
        match group_source:
            case 'ACTIONS':
                if action is None:
                    return None
                action_psa_export = typing_cast(PSX_PG_action_export, getattr(action, 'psa_export'))
                return action_psa_export.group
            case 'CUSTOM':
                return group_custom
            case _:
                return None

    match pg.sequence_source:
        case 'ACTIONS':
            for action_item in filter(lambda x: x.is_selected, pg.action_list):
                if action_item.action is None:
                    continue
                if len(action_item.action.layers) == 0:
                    continue
                export_sequence = PsaBuildSequence(context.active_object, animation_data)
                export_sequence.name = action_item.name
                export_sequence.group = get_export_sequence_group(pg.group_source, pg.group_custom, action_item.action)
                export_sequence.nla_state.action = action_item.action
                export_sequence.nla_state.frame_start = action_item.frame_start
                export_sequence.nla_state.frame_end = action_item.frame_end
                export_sequence.fps = get_sequence_fps(context, pg.fps_source, pg.fps_custom, [action_item.action])
                export_sequence.compression_ratio = get_sequence_compression_ratio(pg.compression_ratio_source, pg.compression_ratio_custom, [action_item.action])
                export_sequence.key_quota = action_item.action.psa_export.key_quota
                export_sequences.append(export_sequence)
        case 'TIMELINE_MARKERS':
            for marker_item in filter(lambda x: x.is_selected, pg.marker_list):
                nla_strips_actions: List[Action] = []
                for nla_strip in get_nla_strips_in_frame_range(animation_data, marker_item.frame_start, marker_item.frame_end):
                    if nla_strip.action:
                        nla_strips_actions.append(nla_strip.action)
                export_sequence = PsaBuildSequence(context.active_object, animation_data)
                export_sequence.name = marker_item.name
                export_sequence.group = get_export_sequence_group(pg.group_source, pg.group_custom, next(iter(nla_strips_actions), None))
                export_sequence.nla_state.frame_start = marker_item.frame_start
                export_sequence.nla_state.frame_end = marker_item.frame_end
                export_sequence.fps = get_sequence_fps(context, pg.fps_source, pg.fps_custom, nla_strips_actions)
                export_sequence.compression_ratio = get_sequence_compression_ratio(pg.compression_ratio_source, pg.compression_ratio_custom, nla_strips_actions)
                export_sequences.append(export_sequence)
        case 'NLA_TRACK_STRIPS':
            for nla_strip_item in filter(lambda x: x.is_selected, pg.nla_strip_list):
                if nla_strip_item.action is None:
                    continue
                export_sequence = PsaBuildSequence(context.active_object, animation_data)
                export_sequence.name = nla_strip_item.name
                export_sequence.group = get_export_sequence_group(pg.group_source, pg.group_custom, nla_strip_item.action)
                export_sequence.nla_state.frame_start = nla_strip_item.frame_start
                export_sequence.nla_state.frame_end = nla_strip_item.frame_end
                export_sequence.fps = get_sequence_fps(context, pg.fps_source, pg.fps_custom, [nla_strip_item.action])
                export_sequence.compression_ratio = get_sequence_compression_ratio(pg.compression_ratio_source, pg.compression_ratio_custom, [nla_strip_item.action])
                export_sequence.key_quota = nla_strip_item.action.psa_export.key_quota
                export_sequences.append(export_sequence)
        case 'ACTIVE_ACTION':
            for active_action_item in filter(lambda x: x.is_selected, pg.active_action_list):
                export_sequence = PsaBuildSequence(active_action_item.armature_object, active_action_item.armature_object.animation_data)
                action = active_action_item.action
                if action is None:
                    continue
                export_sequence.name = action.name
                export_sequence.group = get_export_sequence_group(pg.group_source, pg.group_custom, action)
                export_sequence.nla_state.action = action
                export_sequence.nla_state.frame_start = int(action.frame_range[0])
                export_sequence.nla_state.frame_end = int(action.frame_range[1])
                export_sequence.fps = get_sequence_fps(context, pg.fps_source, pg.fps_custom, [action])
                export_sequence.compression_ratio = get_sequence_compression_ratio(pg.compression_ratio_source, pg.compression_ratio_custom, [action])
                export_sequence.key_quota = action.psa_export.key_quota
                export_sequences.append(export_sequence)
        case _:
            assert False, f'Invalid sequence source: {pg.sequence_source}'

    options = PsaBuildOptions()
    options.armature_objects = list(armature_objects)
    options.animation_data = animation_data
    options.sequences = export_sequences
    options.bone_filter_mode = pg.bone_filter_mode
    options.bone_collection_indices = [PsxBoneCollection(x.armature_object_name, x.armature_data_name, x.index) for x in pg.bone_collection_list if x.is_selected]
    options.sequence_name_prefix = pg.sequence_name_prefix
    options.sequence_name_suffix = pg.sequence_name_suffix
    options.sampling_mode = pg.sampling_mode
    options.export_space = pg.export_space
    options.scale = pg.scale
    options.forward_axis = pg.forward_axis
    options.up_axis = pg.up_axis
    options.root_bone_name = pg.root_bone_name
    options.sequence_source = pg.sequence_source

    return options


class PSA_OT_export(Operator, ExportHelper):
    bl_idname = 'psa.export'
    bl_label = 'Export'
    bl_options = {'INTERNAL'}
    bl_description = 'Export actions to PSA'
    filename_ext = '.psa'
    filter_glob: StringProperty(default='*.psa', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSA file',
        maxlen=1024,
        default='')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.armature_objects: List[Object] = []

    @classmethod
    def poll(cls, context):
        try:
            cls._check_context(context)
        except RuntimeError as e:
            cls.poll_message_set(str(e))
            return False
        return True

    def draw(self, context):
        layout = self.layout
        assert layout
        pg = typing_cast(PSA_PG_export, getattr(context.scene, 'psa_export'))

        # SEQUENCES
        draw_sequences_panel(layout, pg,
                             PSA_OT_export_sequences_select_all.bl_idname, 
                             PSA_OT_export_sequences_deselect_all.bl_idname)

        # BONES
        bones_header, bones_panel = layout.panel('Bones', default_closed=False)
        bones_header.label(text='Bones', icon='BONE_DATA')
        if bones_panel:
            row = bones_panel.row(align=True)

            draw_bone_filter_mode(row, pg)

            if pg.bone_filter_mode == 'BONE_COLLECTIONS':
                row = bones_panel.row(align=True)
                row.label(text='Select')
                row.operator(PSA_OT_export_bone_collections_select_all.bl_idname, text='All', icon='CHECKBOX_HLT')
                row.operator(PSA_OT_export_bone_collections_deselect_all.bl_idname, text='None', icon='CHECKBOX_DEHLT')
                rows = max(3, min(len(pg.bone_collection_list), 10))
                bones_panel.template_list(
                    'PSX_UL_bone_collection_list', '', pg, 'bone_collection_list', pg, 'bone_collection_list_index',
                    rows=rows
                    )

            bones_advanced_header, bones_advanced_panel = bones_panel.panel('Bones Advanced', default_closed=True)
            bones_advanced_header.label(text='Advanced')
            if bones_advanced_panel:
                flow = bones_advanced_panel.grid_flow()
                flow.use_property_split = True
                flow.use_property_decorate = False
                flow.prop(pg, 'root_bone_name', text='Root Bone Name')

        # TRANSFORM
        transform_header, transform_panel = layout.panel('Advanced', default_closed=False)
        transform_header.label(text='Transform', icon='DRIVER_TRANSFORM')

        if transform_panel:
            flow = transform_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'export_space')
            flow.prop(pg, 'scale')
            flow.prop(pg, 'forward_axis')
            flow.prop(pg, 'up_axis')

    @classmethod
    def _check_context(cls, context):
        if context.view_layer.objects.active is None:
            raise RuntimeError('An armature must be selected')

        if context.view_layer.objects.active.type != 'ARMATURE':
            raise RuntimeError('The active object must be an armature')

        if context.scene.is_nla_tweakmode:
            raise RuntimeError('Cannot export PSA while in NLA tweak mode')

    def invoke(self, context, event):
        try:
            self._check_context(context)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        pg: PSA_PG_export = getattr(context.scene, 'psa_export')

        assert context.view_layer is not None

        self.armature_objects = [x for x in context.view_layer.objects.selected if x.type == 'ARMATURE']

        for armature_object in self.armature_objects:
            # This is required otherwise the action list will be empty if the armature has never had its animation
            # data created before (i.e. if no action was ever assigned to it).
            if armature_object.animation_data is None:
                armature_object.animation_data_create()


        pg = getattr(context.scene, 'psa_export')
        update_actions_and_timeline_markers(context, self.armature_objects, pg)
        populate_bone_collection_list(
            pg.bone_collection_list,
            self.armature_objects,
            primary_key='DATA' if pg.sequence_source == 'ACTIVE_ACTION' else 'OBJECT',
            )

        if context.window_manager is not None:
            context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        pg = typing_cast(PSA_PG_export, getattr(context.scene, 'psa_export'))
        options = create_psa_export_options(context, self.armature_objects, pg)

        if len(options.sequences) == 0:
            self.report({'ERROR'}, 'No sequences were selected for export')
            return {'CANCELLED'}

        try:
            psa = build_psa(context, options)
            self.report({'INFO'}, f'PSA export successful')
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        write_psa_to_file(psa, self.filepath)

        return {'FINISHED'}


class PsaExportActionsSelectOperator(Operator):
    @classmethod
    @abstractmethod
    def get_psa_export(cls, context: Context) -> PsaExportMixin:
        pass

    @classmethod
    def get_item_list(cls, context: Context):
        pg = cls.get_psa_export(context)
        match pg.sequence_source:
            case 'ACTIONS':
                return pg.action_list
            case 'TIMELINE_MARKERS':
                return pg.marker_list
            case 'NLA_TRACK_STRIPS':
                return pg.nla_strip_list
            case 'ACTIVE_ACTION':
                return pg.active_action_list
            case _:
                assert False, f'Invalid sequence source: {pg.sequence_source}'

class PsaExportActionsSelectAllOperator(PsaExportActionsSelectOperator):
    def execute(self, context):
        pg = self.__class__.get_psa_export(context)
        sequences = self.get_item_list(context)
        for sequence in get_visible_sequences(pg, sequences):
            sequence.is_selected = True
        return {'FINISHED'}


class PSA_OT_export_sequences_select_all(PsaExportActionsSelectAllOperator):
    bl_idname = 'psa.export_actions_select_all'
    bl_label = 'Select All'
    bl_description = 'Select all visible sequences'
    bl_options = {'INTERNAL'}

    @classmethod
    def get_psa_export(cls, context: Context) -> PsaExportMixin:
        return typing_cast(PsaExportMixin, getattr(context.scene, 'psa_export'))


class PSA_OT_export_collection_sequences_select_all(PsaExportActionsSelectAllOperator):
    bl_idname = 'psa.export_collection_sequences_select_all'
    bl_label = 'Select All'
    bl_description = 'Select all visible sequences'
    bl_options = {'INTERNAL'}

    @classmethod
    def get_psa_export(cls, context: Context) -> PsaExportMixin:
        operator = get_collection_export_operator_from_context(context)
        operator = typing_cast(PsaExportMixin, operator)
        return operator


class PsaExportActionsDeselectAllOperator(PsaExportActionsSelectOperator):
    def execute(self, context):
        pg = getattr(context.scene, 'psa_export')
        item_list = self.get_item_list(context)
        for sequence in get_visible_sequences(pg, item_list):
            sequence.is_selected = False
        return {'FINISHED'}


class PSA_OT_export_collection_sequences_deselect_all(PsaExportActionsDeselectAllOperator):
    bl_idname = 'psa.export_collection_sequences_deselect_all'
    bl_label = 'Deselect All'
    bl_description = 'Deselect all visible sequences'
    bl_options = {'INTERNAL'}

    @classmethod
    def get_psa_export(cls, context: Context) -> PsaExportMixin:
        operator = get_collection_export_operator_from_context(context)
        operator = typing_cast(PsaExportMixin, operator)
        return operator


class PSA_OT_export_sequences_deselect_all(PsaExportActionsDeselectAllOperator):
    bl_idname = 'psa.export_sequences_deselect_all'
    bl_label = 'Deselect All'
    bl_description = 'Deselect all visible sequences'
    bl_options = {'INTERNAL'}

    @classmethod
    def get_psa_export(cls, context: Context) -> PsaExportMixin:
        return typing_cast(PsaExportMixin, getattr(context.scene, 'psa_export'))


class PSA_OT_export_bone_collections_select_all(Operator):
    bl_idname = 'psa.export_bone_collections_select_all'
    bl_label = 'Select All'
    bl_description = 'Select all bone collections'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        pg = typing_cast(PSA_PG_export, getattr(context.scene, 'psa_export'))
        item_list = pg.bone_collection_list
        has_unselected_items = any(map(lambda action: not action.is_selected, item_list))
        return len(item_list) > 0 and has_unselected_items

    def execute(self, context):
        pg = typing_cast(PSA_PG_export, getattr(context.scene, 'psa_export'))
        for item in pg.bone_collection_list:
            item.is_selected = True
        return {'FINISHED'}


class PSA_OT_export_bone_collections_deselect_all(Operator):
    bl_idname = 'psa.export_bone_collections_deselect_all'
    bl_label = 'Deselect All'
    bl_description = 'Deselect all bone collections'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        pg = typing_cast(PSA_PG_export, getattr(context.scene, 'psa_export'))
        item_list = pg.bone_collection_list
        has_selected_actions = any(map(lambda action: action.is_selected, item_list))
        return len(item_list) > 0 and has_selected_actions

    def execute(self, context):
        pg = typing_cast(PSA_PG_export, getattr(context.scene, 'psa_export'))
        for action in pg.bone_collection_list:
            action.is_selected = False
        return {'FINISHED'}


class PSA_OT_export_collection_populate_sequences(Operator):
    bl_idname = 'psa.export_collection_populate_sequences'
    bl_label = 'Populate Sequences'
    bl_description = 'Populate the sequences list based on the armatures in the collection'
    bl_options = {'INTERNAL'}

    def execute(self, context: Context):
        export_operator = get_collection_export_operator_from_context(context)
        assert export_operator is not None
        export_operator = typing_cast(PSA_OT_export_collection, export_operator)
        collection = get_collection_from_context(context)
        if collection is None:
            self.report({'ERROR'}, 'No collection found in context')
            return {'CANCELLED'}
        
        try:
            input_objects = get_psk_input_objects_for_collection(collection)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        # Keep track of what sequences were selected, then restore the selected status after we have updated the lists.
        def store_is_selected_for_sequence_list(sequences: Iterable[PsaExportSequenceMixin]) -> dict[int, bool]:
            return {hash(x): x.is_selected for x in sequences}
    
        def restore_is_selected_for_sequence_list(sequence_list: Iterable[PsaExportSequenceMixin], is_selected_map: dict[int, bool]):
            for sequence in sequence_list:
                sequence.is_selected = is_selected_map.get(hash(sequence), False)

        action_list_is_selected = store_is_selected_for_sequence_list(export_operator.action_list)
        markers_list_is_selected = store_is_selected_for_sequence_list(export_operator.marker_list)
        nla_strip_list_is_selected = store_is_selected_for_sequence_list(export_operator.nla_strip_list)
        active_action_list_is_selected = store_is_selected_for_sequence_list(export_operator.active_action_list)

        update_actions_and_timeline_markers(context, input_objects.armature_objects, export_operator)

        restore_is_selected_for_sequence_list(export_operator.action_list, action_list_is_selected)
        restore_is_selected_for_sequence_list(export_operator.marker_list, markers_list_is_selected)
        restore_is_selected_for_sequence_list(export_operator.nla_strip_list, nla_strip_list_is_selected)
        restore_is_selected_for_sequence_list(export_operator.active_action_list, active_action_list_is_selected)
        
        return {'FINISHED'}


_classes = (
    PSA_OT_export,
    PSA_OT_export_collection,
    PSA_OT_export_sequences_select_all,
    PSA_OT_export_sequences_deselect_all,
    PSA_OT_export_collection_sequences_select_all,
    PSA_OT_export_collection_sequences_deselect_all,
    PSA_OT_export_bone_collections_select_all,
    PSA_OT_export_bone_collections_deselect_all,
    PSA_OT_export_collection_populate_sequences,
)

from bpy.utils import register_classes_factory
register, unregister = register_classes_factory(_classes)

