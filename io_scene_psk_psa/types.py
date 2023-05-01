import bpy.props
from bpy.props import StringProperty, IntProperty, BoolProperty, FloatProperty
from bpy.types import PropertyGroup, UIList, UILayout, Context, AnyType, Operator, Panel


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


class PSX_PG_ActionExportPropertyGroup(PropertyGroup):
    compression_ratio: FloatProperty(name='Compression Ratio', default=1.0, min=0.0, max=1.0, subtype='FACTOR', description='The ratio of frames to be exported.\n\nA compression ratio of 1.0 will export all frames, while a compression ratio of 0.5 will export half of the frames')
    key_quota: IntProperty(name='Key Quota', default=0, min=1, description='The minimum number of frames to be exported')


class PSX_PT_ActionPropertyPanel(Panel):
    bl_idname = 'PSX_PT_ActionPropertyPanel'
    bl_label = 'PSA Export'
    bl_space_type = 'DOPESHEET_EDITOR'
    bl_region_type = 'UI'
    bl_context = 'action'
    bl_category = 'Action'

    @classmethod
    def poll(cls, context: 'Context'):
        return context.active_object and context.active_object.type == 'ARMATURE' and context.active_action is not None

    def draw(self, context: 'Context'):
        action = context.active_action
        layout = self.layout
        layout.prop(action.psa_export, 'compression_ratio')
        layout.prop(action.psa_export, 'key_quota')


classes = (
    PSX_PG_ActionExportPropertyGroup,
    BoneGroupListItem,
    PSX_UL_BoneGroupList,
    PSX_UL_MaterialPathList,
    PSX_OT_MaterialPathAdd,
    PSX_OT_MaterialPathRemove,
    PSX_PT_ActionPropertyPanel
)
