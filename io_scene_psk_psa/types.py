from bpy.types import PropertyGroup, UIList
from bpy.props import StringProperty, IntProperty, BoolProperty


class PSX_UL_BoneGroupList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.alignment = 'LEFT'
        layout.prop(item, 'is_selected', icon_only=True)
        layout.label(text=item.name, icon='GROUP_BONE' if item.index >= 0 else 'NONE')


class BoneGroupListItem(PropertyGroup):
    name: StringProperty()
    index: IntProperty()
    is_selected: BoolProperty(default=False)

    @property
    def name(self):
        return self.name


__classes__ = [
    BoneGroupListItem,
    PSX_UL_BoneGroupList
]
