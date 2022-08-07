from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy.types import PropertyGroup, UIList, UILayout, Context, AnyType


class PSX_UL_BoneGroupList(UIList):

    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        row.prop(item, 'is_selected', text=getattr(item, 'name'))
        row.label(text=str(getattr(item, 'count')), icon='BONE_DATA')


class BoneGroupListItem(PropertyGroup):
    name: StringProperty()
    index: IntProperty()
    count: IntProperty()
    is_selected: BoolProperty(default=False)


classes = (
    BoneGroupListItem,
    PSX_UL_BoneGroupList,
)
