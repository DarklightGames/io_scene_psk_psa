import bpy
from bpy.types import UIList

from .properties import filter_sequences


class PSA_UL_sequences_mixin(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        row = layout.row(align=True)
        split = row.split(align=True, factor=0.75)
        column = split.row(align=True)
        column.alignment = 'LEFT'
        column.prop(item, 'is_selected', icon_only=True)
        column.label(text=getattr(item, 'action_name'))

    def draw_filter(self, context, layout):
        pg = getattr(context.scene, 'psa_import')
        row = layout.row()
        sub_row = row.row(align=True)
        sub_row.prop(pg, 'sequence_filter_name', text='')
        sub_row.prop(pg, 'sequence_use_filter_invert', text='', icon='ARROW_LEFTRIGHT')
        sub_row.prop(pg, 'sequence_use_filter_regex', text='', icon='SORTBYEXT')
        sub_row.prop(pg, 'sequence_filter_is_selected', text='', icon='CHECKBOX_HLT')

    def filter_items(self, context, data, property_):
        pg = getattr(context.scene, 'psa_import')
        sequences = getattr(data, property_)
        flt_flags = filter_sequences(pg, sequences)
        flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(sequences, 'action_name')
        return flt_flags, flt_neworder


class PSA_UL_sequences(PSA_UL_sequences_mixin):
    pass


class PSA_UL_import_sequences(PSA_UL_sequences_mixin):
    pass


class PSA_UL_import_actions(PSA_UL_sequences_mixin):
    pass


classes = (
    PSA_UL_sequences,
    PSA_UL_import_sequences,
    PSA_UL_import_actions,
)
