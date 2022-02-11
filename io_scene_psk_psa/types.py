from bpy.types import PropertyGroup, UIList
from bpy.props import StringProperty, IntProperty, BoolProperty


class PSX_UL_BoneGroupList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row()
        row.prop(item, 'is_selected', text=item.name)
        row.label(text=str(item.count), icon='BONE_DATA')


class BoneGroupListItem(PropertyGroup):
    name: StringProperty()
    index: IntProperty()
    count: IntProperty()
    is_selected: BoolProperty(default=False)

    @property
    def name(self):
        return self.name


classes = (
    BoneGroupListItem,
    PSX_UL_BoneGroupList,
)
