from bpy.props import StringProperty, IntProperty, BoolProperty, FloatProperty
from bpy.types import PropertyGroup, UIList, UILayout, Context, AnyType, Panel


class PSX_UL_bone_collection_list(UIList):

    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        row.prop(item, 'is_selected', text=getattr(item, 'name'))
        row.label(text=str(getattr(item, 'count')), icon='BONE_DATA')


class PSX_PG_bone_collection_list_item(PropertyGroup):
    name: StringProperty()
    index: IntProperty()
    count: IntProperty()
    is_selected: BoolProperty(default=False)


class PSX_PG_action_export(PropertyGroup):
    compression_ratio: FloatProperty(name='Compression Ratio', default=1.0, min=0.0, max=1.0, subtype='FACTOR', description='The key sampling ratio of the exported sequence.\n\nA compression ratio of 1.0 will export all frames, while a compression ratio of 0.5 will export half of the frames')
    key_quota: IntProperty(name='Key Quota', default=0, min=1, description='The minimum number of frames to be exported')
    fps: FloatProperty(name='FPS', default=30.0, min=0.0, description='The frame rate of the exported sequence')


class PSX_PT_action(Panel):
    bl_idname = 'PSX_PT_action'
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
        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(action.psa_export, 'compression_ratio')
        flow.prop(action.psa_export, 'key_quota')
        flow.prop(action.psa_export, 'fps')


classes = (
    PSX_PG_action_export,
    PSX_PG_bone_collection_list_item,
    PSX_UL_bone_collection_list,
    PSX_PT_action,
)
