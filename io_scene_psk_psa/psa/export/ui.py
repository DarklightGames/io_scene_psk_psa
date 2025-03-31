from typing import cast as typing_cast

from bpy.types import UIList

from .properties import PSA_PG_export_action_list_item, filter_sequences


class PSA_UL_export_sequences(UIList):
    bl_idname = 'PSA_UL_export_sequences'

    def __init__(self, *args, **kwargs):
        super(PSA_UL_export_sequences, self).__init__(*args, **kwargs)
        # Show the filtering options by default.
        self.use_filter_show = True

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        item = typing_cast(PSA_PG_export_action_list_item, item)

        is_pose_marker = hasattr(item, 'is_pose_marker') and item.is_pose_marker
        layout.prop(item, 'is_selected', icon_only=True, text=item.name)
        if hasattr(item, 'action') and item.action is not None and item.action.asset_data is not None:
            layout.label(text='', icon='ASSET_MANAGER')

        row = layout.row(align=True)
        row.alignment = 'RIGHT'

        row.label(text=str(abs(item.frame_end - item.frame_start) + 1), icon='FRAME_PREV' if item.frame_end < item.frame_start else 'KEYFRAME')

        if hasattr(item, 'armature_object') and item.armature_object is not None:
            row.label(text=item.armature_object.name, icon='ARMATURE_DATA')

        # row.label(text=item.action.name, icon='PMARKER' if is_pose_marker else 'ACTION_DATA')

    def draw_filter(self, context, layout):
        pg = getattr(context.scene, 'psa_export')
        row = layout.row()
        subrow = row.row(align=True)
        subrow.prop(pg, 'sequence_filter_name', text='')
        subrow.prop(pg, 'sequence_use_filter_invert', text='', icon='ARROW_LEFTRIGHT')

        if pg.sequence_source == 'ACTIONS':
            subrow = row.row(align=True)
            subrow.prop(pg, 'sequence_filter_asset', icon_only=True, icon='ASSET_MANAGER')
            subrow.prop(pg, 'sequence_filter_pose_marker', icon_only=True, icon='PMARKER')
            subrow.prop(pg, 'sequence_filter_reversed', text='', icon='FRAME_PREV')

    def filter_items(self, context, data, prop):
        pg = getattr(context.scene, 'psa_export')
        actions = getattr(data, prop)
        flt_flags = filter_sequences(pg, actions)
        flt_neworder = list(range(len(actions)))
        return flt_flags, flt_neworder


classes = (
    PSA_UL_export_sequences,
)
