import bpy
from bpy.types import UIList


class PSK_UL_material_names(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        material = bpy.data.materials.get(item.material_name, None)
        icon_value = layout.icon(material) if material else 0
        row.prop(item, 'material_name', text='', emboss=False, icon_value=icon_value, icon='BLANK1' if icon_value == 0 else 'NONE')


_classes = (
    PSK_UL_material_names,
)

from bpy.utils import register_classes_factory
register, unregister = register_classes_factory(_classes)
