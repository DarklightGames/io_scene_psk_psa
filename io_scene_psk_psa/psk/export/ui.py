import bpy
from bpy.types import UIList
from typing import cast as typing_cast

from .properties import PSK_PG_material_name_list_item


class PSK_UL_material_names(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        # Split the row into fixed-width halves so that the arrow and export name line up across all rows, regardless
        # of what is drawn on the name side.
        split = layout.split(factor=0.5)
        item = typing_cast(PSK_PG_material_name_list_item, item)
        material = bpy.data.materials.get(item.material_name, None)

        # If the material is not found by name and the name is not 'None', show a not found icon
        if item.material_name == 'None':
            icon = 'NODE_MATERIAL'
        else:
            icon = 'NOT_FOUND' if material is None else 'NONE'

        name_row = split.row()
        if material is not None:
            name_row.label(text=item.material_name, icon_value=layout.icon(material))
        else:
            name_row.label(text=item.material_name, icon=icon)

        # Add right-aligned "Not Found" label if material is not found
        if item.material_name != 'None' and material is None:
            label_row = name_row.row()
            label_row.alignment = 'RIGHT'
            label_row.enabled = False
            label_row.label(text='Not Found')

        has_export_name = item.material_name != item.export_name

        export_row = split.row()
        arrow_row = export_row.row()
        arrow_row.enabled = has_export_name
        arrow_row.ui_units_x = 1
        arrow_row.label(icon='TRIA_RIGHT' if has_export_name else 'RIGHTARROW', text='')
        export_row.prop(item, 'export_name', text='', emboss=False)

_classes = (
    PSK_UL_material_names,
)

from bpy.utils import register_classes_factory
register, unregister = register_classes_factory(_classes)
