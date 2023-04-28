import bpy.props
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy.types import PropertyGroup, UIList, UILayout, Context, AnyType, Operator


class PSX_UL_BoneGroupList(UIList):

    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        row.prop(item, 'is_selected', text=getattr(item, 'name'))
        row.label(text=str(getattr(item, 'count')), icon='BONE_DATA')


class PSX_OT_MaterialPathAdd(Operator):
    bl_idname = 'psx.material_paths_add'
    bl_label = 'Add Material Path'
    bl_options = {'INTERNAL'}

    directory: bpy.props.StringProperty(subtype='DIR_PATH', options={'HIDDEN'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'})

    def invoke(self, context: 'Context', event: 'Event'):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: 'Context'):
        m = context.preferences.addons[__package__].preferences.material_path_list.add()
        m.path = self.directory
        return {'FINISHED'}


class PSX_OT_MaterialPathRemove(Operator):
    bl_idname = 'psx.material_paths_remove'
    bl_label = 'Remove Material Path'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context: 'Context'):
        preferences = context.preferences.addons[__package__].preferences
        return preferences.material_path_index >= 0

    def execute(self, context: 'Context'):
        preferences = context.preferences.addons[__package__].preferences
        preferences.material_path_list.remove(preferences.material_path_index)
        return {'FINISHED'}


class PSX_UL_MaterialPathList(UIList):

    def draw_item(self,
                  context: 'Context',
                  layout: 'UILayout',
                  data: 'AnyType',
                  item: 'AnyType',
                  icon: int,
                  active_data: 'AnyType',
                  active_property: str,
                  index: int = 0,
                  flt_flag: int = 0):
        row = layout.row()
        row.label(text=getattr(item, 'path'))


class BoneGroupListItem(PropertyGroup):
    name: StringProperty()
    index: IntProperty()
    count: IntProperty()
    is_selected: BoolProperty(default=False)


classes = (
    BoneGroupListItem,
    PSX_UL_BoneGroupList,
    PSX_UL_MaterialPathList,
    PSX_OT_MaterialPathAdd,
    PSX_OT_MaterialPathRemove
)
