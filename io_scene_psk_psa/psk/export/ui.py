import bpy
from bpy.types import UIList
from typing import cast as typing_cast

from .properties import PSK_PG_material_name_list_item


class PSK_UL_material_names(UIList):
    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_property,
        index,
        flt_flag
    ):
        row = layout.row()
        item = typing_cast(PSK_PG_material_name_list_item, item)
        material = bpy.data.materials.get(item.material_name, None)

        # If the material is not found by name and the name is not 'None', show a not found icon
        if item.material_name == 'None':
            icon = 'NODE_MATERIAL'
        else:
            icon = 'NOT_FOUND' if material is None else 'NONE'

        row.prop(item, 'material_name', text='', emboss=False,
                 icon_value=layout.icon(material) if material else 0,
                 icon=icon)

        # Add right-aligned "Not Found" label if material is not found
        if item.material_name != 'None' and material is None:
            label_row = row.row()
            label_row.alignment = 'RIGHT'
            label_row.enabled = False
            label_row.label(text='Not Found')


_classes = (
    PSK_UL_material_names,
)

from bpy.utils import register_classes_factory
register, unregister = register_classes_factory(_classes)
