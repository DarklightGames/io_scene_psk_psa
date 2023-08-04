from bpy.types import UIList


class PSK_UL_materials(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        row.label(text=item.material_name, icon='MATERIAL', translate=False)


classes = (
    PSK_UL_materials,
)
