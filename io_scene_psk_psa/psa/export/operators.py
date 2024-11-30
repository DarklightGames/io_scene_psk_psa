import re
from collections import Counter
from typing import List, Iterable, Dict, Tuple

import bpy
from bpy.props import StringProperty
from bpy.types import Context, Armature, Action, Object, AnimData, TimelineMarker
from bpy_extras.io_utils import ExportHelper
from bpy_types import Operator

from .properties import PSA_PG_export, PSA_PG_export_action_list_item, filter_sequences, \
    get_sequences_from_name_and_frame_range
from ..builder import build_psa, PsaBuildSequence, PsaBuildOptions
from ..writer import write_psa
from ...shared.helpers import populate_bone_collection_list, get_nla_strips_in_frame_range
from ...shared.ui import draw_bone_filter_mode


def is_action_for_armature(armature: Armature, action: Action):
    if len(action.fcurves) == 0:
        return False
    bone_names = set([x.name for x in armature.bones])
    for fcurve in action.fcurves:
        match = re.match(r'pose\.bones\[\"([^\"]+)\"](\[\"([^\"]+)\"])?', fcurve.data_path)
        if not match:
            continue
        bone_name = match.group(1)
        if bone_name in bone_names:
            return True
    return False


def update_actions_and_timeline_markers(context: Context, armature: Armature):
    pg = getattr(context.scene, 'psa_export')

    # Clear actions and markers.
    pg.action_list.clear()
    pg.marker_list.clear()

    # Get animation data.
    animation_data_object = get_animation_data_object(context)
    animation_data = animation_data_object.animation_data if animation_data_object else None

    if animation_data is None:
        return

    # Populate actions list.
    for action in bpy.data.actions:
        if not is_action_for_armature(armature, action):
            continue

        if action.name != '' and not action.name.startswith('#'):
            for (name, frame_start, frame_end) in get_sequences_from_action(action):
                item = pg.action_list.add()
                item.action = action
                item.name = name
                item.is_selected = False
                item.is_pose_marker = False
                item.frame_start = frame_start
                item.frame_end = frame_end

        # Pose markers are not guaranteed to be in frame-order, so make sure that they are.
        pose_markers = sorted(action.pose_markers, key=lambda x: x.frame)
        for pose_marker_index, pose_marker in enumerate(pose_markers):
            if pose_marker.name.strip() == '' or pose_marker.name.startswith('#'):
                continue
            for (name, frame_start, frame_end) in get_sequences_from_action_pose_markers(action, pose_markers, pose_marker, pose_marker_index):
                item = pg.action_list.add()
                item.action = action
                item.name = name
                item.is_selected = False
                item.is_pose_marker = True
                item.frame_start = frame_start
                item.frame_end = frame_end

    # Populate timeline markers list.
    marker_names = [x.name for x in context.scene.timeline_markers]
    sequence_frame_ranges = get_timeline_marker_sequence_frame_ranges(animation_data, context, marker_names)

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


def get_sequence_fps(context: Context, fps_source: str, fps_custom: float, actions: Iterable[Action]) -> float:
    match fps_source:
        case 'SCENE':
            return context.scene.render.fps
        case 'CUSTOM':
            return fps_custom
        case 'ACTION_METADATA':
            # Get the minimum value of action metadata FPS values.
            return min([action.psa_export.fps for action in actions])
        case _:
            raise RuntimeError(f'Invalid FPS source "{fps_source}"')


def get_animation_data_object(context: Context) -> Object:
    pg: PSA_PG_export = getattr(context.scene, 'psa_export')

    active_object = context.view_layer.objects.active

    if active_object.type != 'ARMATURE':
        raise RuntimeError('Selected object must be an Armature')

    if pg.sequence_source != 'ACTIONS' and pg.should_override_animation_data:
        animation_data_object = pg.animation_data_override
    else:
        animation_data_object = active_object

    return animation_data_object


def get_timeline_marker_sequence_frame_ranges(animation_data: AnimData, context: Context, marker_names: List[str]) -> Dict:
    # Timeline markers need to be sorted so that we can determine the sequence start and end positions.
    sequence_frame_ranges = dict()
    sorted_timeline_markers = list(sorted(context.scene.timeline_markers, key=lambda x: x.frame))
    sorted_timeline_marker_names = [x.name for x in sorted_timeline_markers]

    for marker_name in marker_names:
        marker = context.scene.timeline_markers[marker_name]
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


def get_sequences_from_action(action: Action) -> List[Tuple[str, int, int]]:
    frame_start = int(action.frame_range[0])
    frame_end = int(action.frame_range[1])
    return get_sequences_from_name_and_frame_range(action.name, frame_start, frame_end)


def get_sequences_from_action_pose_markers(action: Action, pose_markers: List[TimelineMarker], pose_marker: TimelineMarker, pose_marker_index: int) -> List[Tuple[str, int, int]]:
    frame_start = pose_marker.frame
    sequence_name = pose_marker.name
    if pose_marker.name.startswith('!'):
        # If the pose marker name starts with an exclamation mark, only export the first frame.
        frame_end = frame_start
        sequence_name = sequence_name[1:]
    elif pose_marker_index + 1 < len(pose_markers):
        frame_end = pose_markers[pose_marker_index + 1].frame
    else:
        frame_end = int(action.frame_range[1])
    return get_sequences_from_name_and_frame_range(sequence_name, frame_start, frame_end)


def get_visible_sequences(pg: PSA_PG_export, sequences) -> List[PSA_PG_export_action_list_item]:
    visible_sequences = []
    for i, flag in enumerate(filter_sequences(pg, sequences)):
        if bool(flag & (1 << 30)):
            visible_sequences.append(sequences[i])
    return visible_sequences


class PSA_OT_export(Operator, ExportHelper):
    bl_idname = 'psa_export.operator'
    bl_label = 'Export'
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = 'Export actions to PSA'
    filename_ext = '.psa'
    filter_glob: StringProperty(default='*.psa', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSA file',
        maxlen=1024,
        default='')

    def __init__(self):
        self.armature_object = None

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
        pg = getattr(context.scene, 'psa_export')

        sequences_header, sequences_panel = layout.panel('Sequences', default_closed=False)
        sequences_header.label(text='Sequences', icon='ACTION')

        if sequences_panel:
            flow = sequences_panel.grid_flow()
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'sequence_source', text='Source')

            if pg.sequence_source in {'TIMELINE_MARKERS', 'NLA_TRACK_STRIPS'}:
                # ANIMDATA SOURCE
                flow.prop(pg, 'should_override_animation_data')
                if pg.should_override_animation_data:
                    flow.prop(pg, 'animation_data_override', text=' ')

            if pg.sequence_source == 'NLA_TRACK_STRIPS':
                flow = sequences_panel.grid_flow()
                flow.use_property_split = True
                flow.use_property_decorate = False
                flow.prop(pg, 'nla_track')

            # SELECT ALL/NONE
            row = sequences_panel.row(align=True)
            row.label(text='Select')
            row.operator(PSA_OT_export_actions_select_all.bl_idname, text='All', icon='CHECKBOX_HLT')
            row.operator(PSA_OT_export_actions_deselect_all.bl_idname, text='None', icon='CHECKBOX_DEHLT')

            from .ui import PSA_UL_export_sequences

            def get_sequences_propnames_from_source(sequence_source: str) -> Tuple[str, str]:
                match sequence_source:
                    case 'ACTIONS':
                        return 'action_list', 'action_list_index'
                    case 'TIMELINE_MARKERS':
                        return 'marker_list', 'marker_list_index'
                    case 'NLA_TRACK_STRIPS':
                        return 'nla_strip_list', 'nla_strip_list_index'
                    case _:
                        raise ValueError(f'Unhandled sequence source: {sequence_source}')

            propname, active_propname = get_sequences_propnames_from_source(pg.sequence_source)
            sequences_panel.template_list(PSA_UL_export_sequences.bl_idname, '', pg, propname, pg, active_propname,
                                          rows=max(3, min(len(getattr(pg, propname)), 10)))

            flow = sequences_panel.grid_flow()
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

            # FPS
            flow.prop(pg, 'fps_source')
            if pg.fps_source == 'CUSTOM':
                flow.prop(pg, 'fps_custom', text='Custom')

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
                bones_panel.template_list('PSX_UL_bone_collection_list', '', pg, 'bone_collection_list', pg, 'bone_collection_list_index',
                                     rows=rows)

            flow = bones_panel.grid_flow()
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'should_enforce_bone_name_restrictions')

        # ADVANCED
        advanced_header, advanced_panel = layout.panel('Advanced', default_closed=False)
        advanced_header.label(text='Advanced')

        if advanced_panel:
            flow = advanced_panel.grid_flow()
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'root_motion', text='Root Motion')

    @classmethod
    def _check_context(cls, context):
        if context.view_layer.objects.active is None:
            raise RuntimeError('An armature must be selected')

        if context.view_layer.objects.active.type != 'ARMATURE':
            raise RuntimeError('The selected object must be an armature')

    def invoke(self, context, _event):
        try:
            self._check_context(context)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))

        pg: PSA_PG_export = getattr(context.scene, 'psa_export')

        self.armature_object = context.view_layer.objects.active

        if self.armature_object.animation_data is None:
            # This is required otherwise the action list will be empty if the armature has never had its animation
            # data created before (i.e. if no action was ever assigned to it).
            self.armature_object.animation_data_create()

        update_actions_and_timeline_markers(context, self.armature_object.data)

        populate_bone_collection_list(self.armature_object, pg.bone_collection_list)

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        pg = getattr(context.scene, 'psa_export')

        # Ensure that we actually have items that we are going to be exporting.
        if pg.sequence_source == 'ACTIONS' and len(pg.action_list) == 0:
            raise RuntimeError('No actions were selected for export')
        elif pg.sequence_source == 'TIMELINE_MARKERS' and len(pg.marker_list) == 0:
            raise RuntimeError('No timeline markers were selected for export')
        elif pg.sequence_source == 'NLA_TRACK_STRIPS' and len(pg.nla_strip_list) == 0:
            raise RuntimeError('No NLA track strips were selected for export')

        # Populate the export sequence list.
        animation_data_object = get_animation_data_object(context)
        animation_data = animation_data_object.animation_data

        if animation_data is None:
            raise RuntimeError(f'No animation data for object \'{animation_data_object.name}\'')

        export_sequences: List[PsaBuildSequence] = []

        match pg.sequence_source:
            case 'ACTIONS':
                for action_item in filter(lambda x: x.is_selected, pg.action_list):
                    if len(action_item.action.fcurves) == 0:
                        continue
                    export_sequence = PsaBuildSequence()
                    export_sequence.nla_state.action = action_item.action
                    export_sequence.name = action_item.name
                    export_sequence.nla_state.frame_start = action_item.frame_start
                    export_sequence.nla_state.frame_end = action_item.frame_end
                    export_sequence.fps = get_sequence_fps(context, pg.fps_source, pg.fps_custom, [action_item.action])
                    export_sequence.compression_ratio = action_item.action.psa_export.compression_ratio
                    export_sequence.key_quota = action_item.action.psa_export.key_quota
                    export_sequences.append(export_sequence)
            case 'TIMELINE_MARKERS':
                for marker_item in filter(lambda x: x.is_selected, pg.marker_list):
                    export_sequence = PsaBuildSequence()
                    export_sequence.name = marker_item.name
                    export_sequence.nla_state.action = None
                    export_sequence.nla_state.frame_start = marker_item.frame_start
                    export_sequence.nla_state.frame_end = marker_item.frame_end
                    nla_strips_actions = set(
                        map(lambda x: x.action, get_nla_strips_in_frame_range(animation_data, marker_item.frame_start, marker_item.frame_end)))
                    export_sequence.fps = get_sequence_fps(context, pg.fps_source, pg.fps_custom, nla_strips_actions)
                    export_sequences.append(export_sequence)
            case 'NLA_TRACK_STRIPS':
                for nla_strip_item in filter(lambda x: x.is_selected, pg.nla_strip_list):
                    export_sequence = PsaBuildSequence()
                    export_sequence.name = nla_strip_item.name
                    export_sequence.nla_state.action = None
                    export_sequence.nla_state.frame_start = nla_strip_item.frame_start
                    export_sequence.nla_state.frame_end = nla_strip_item.frame_end
                    export_sequence.fps = get_sequence_fps(context, pg.fps_source, pg.fps_custom, [nla_strip_item.action])
                    export_sequence.compression_ratio = nla_strip_item.action.psa_export.compression_ratio
                    export_sequence.key_quota = nla_strip_item.action.psa_export.key_quota
                    export_sequences.append(export_sequence)
            case _:
                raise ValueError(f'Unhandled sequence source: {pg.sequence_source}')

        options = PsaBuildOptions()
        options.animation_data = animation_data
        options.sequences = export_sequences
        options.bone_filter_mode = pg.bone_filter_mode
        options.bone_collection_indices = [x.index for x in pg.bone_collection_list if x.is_selected]
        options.should_ignore_bone_name_restrictions = pg.should_enforce_bone_name_restrictions
        options.sequence_name_prefix = pg.sequence_name_prefix
        options.sequence_name_suffix = pg.sequence_name_suffix
        options.root_motion = pg.root_motion

        try:
            psa = build_psa(context, options)
            self.report({'INFO'}, f'PSA export successful')
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        write_psa(psa, self.filepath)

        return {'FINISHED'}


class PSA_OT_export_actions_select_all(Operator):
    bl_idname = 'psa_export.sequences_select_all'
    bl_label = 'Select All'
    bl_description = 'Select all visible sequences'
    bl_options = {'INTERNAL'}

    @classmethod
    def get_item_list(cls, context):
        pg = context.scene.psa_export
        match pg.sequence_source:
            case 'ACTIONS':
                return pg.action_list
            case 'TIMELINE_MARKERS':
                return pg.marker_list
            case 'NLA_TRACK_STRIPS':
                return pg.nla_strip_list
            case _:
                return None

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psa_export')
        item_list = cls.get_item_list(context)
        visible_sequences = get_visible_sequences(pg, item_list)
        has_unselected_sequences = any(map(lambda item: not item.is_selected, visible_sequences))
        return has_unselected_sequences

    def execute(self, context):
        pg = getattr(context.scene, 'psa_export')
        sequences = self.get_item_list(context)
        for sequence in get_visible_sequences(pg, sequences):
            sequence.is_selected = True
        return {'FINISHED'}


class PSA_OT_export_actions_deselect_all(Operator):
    bl_idname = 'psa_export.sequences_deselect_all'
    bl_label = 'Deselect All'
    bl_description = 'Deselect all visible sequences'
    bl_options = {'INTERNAL'}

    @classmethod
    def get_item_list(cls, context):
        pg = context.scene.psa_export
        match pg.sequence_source:
            case 'ACTIONS':
                return pg.action_list
            case 'TIMELINE_MARKERS':
                return pg.marker_list
            case 'NLA_TRACK_STRIPS':
                return pg.nla_strip_list
            case _:
                return None

    @classmethod
    def poll(cls, context):
        item_list = cls.get_item_list(context)
        has_selected_items = any(map(lambda item: item.is_selected, item_list))
        return len(item_list) > 0 and has_selected_items

    def execute(self, context):
        pg = getattr(context.scene, 'psa_export')
        item_list = self.get_item_list(context)
        for sequence in get_visible_sequences(pg, item_list):
            sequence.is_selected = False
        return {'FINISHED'}


class PSA_OT_export_bone_collections_select_all(Operator):
    bl_idname = 'psa_export.bone_collections_select_all'
    bl_label = 'Select All'
    bl_description = 'Select all bone collections'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psa_export')
        item_list = pg.bone_collection_list
        has_unselected_items = any(map(lambda action: not action.is_selected, item_list))
        return len(item_list) > 0 and has_unselected_items

    def execute(self, context):
        pg = getattr(context.scene, 'psa_export')
        for item in pg.bone_collection_list:
            item.is_selected = True
        return {'FINISHED'}


class PSA_OT_export_bone_collections_deselect_all(Operator):
    bl_idname = 'psa_export.bone_collections_deselect_all'
    bl_label = 'Deselect All'
    bl_description = 'Deselect all bone collections'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psa_export')
        item_list = pg.bone_collection_list
        has_selected_actions = any(map(lambda action: action.is_selected, item_list))
        return len(item_list) > 0 and has_selected_actions

    def execute(self, context):
        pg = getattr(context.scene, 'psa_export')
        for action in pg.bone_collection_list:
            action.is_selected = False
        return {'FINISHED'}


classes = (
    PSA_OT_export,
    PSA_OT_export_actions_select_all,
    PSA_OT_export_actions_deselect_all,
    PSA_OT_export_bone_collections_select_all,
    PSA_OT_export_bone_collections_deselect_all,
)
