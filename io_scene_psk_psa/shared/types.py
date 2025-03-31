import bpy
from bpy.props import CollectionProperty, EnumProperty, StringProperty, IntProperty, BoolProperty, FloatProperty
from bpy.types import PropertyGroup, UIList, UILayout, Context, AnyType, Panel


class PSX_UL_bone_collection_list(UIList):

    def draw_item(self, _context: Context, layout: UILayout, _data: AnyType, item: AnyType, _icon: int,
                  _active_data: AnyType, _active_property: str, _index: int = 0, _flt_flag: int = 0):
        row = layout.row()

        row.prop(item, 'is_selected', text=getattr(item, 'name'))
        row.label(text=str(getattr(item, 'count')), icon='BONE_DATA')

        armature_object = bpy.data.objects.get(item.armature_object_name, None)
        if armature_object is None:
            row.label(icon='ERROR')
        else:
            row.label(text=armature_object.name, icon='ARMATURE_DATA')


class PSX_PG_bone_collection_list_item(PropertyGroup):
    armature_object_name: StringProperty()
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


bone_filter_mode_items = (
    ('ALL', 'All', 'All bones will be exported'),
    ('BONE_COLLECTIONS', 'Bone Collections', 'Only bones belonging to the selected bone collections and their ancestors will be exported')
)

axis_identifiers = ('X', 'Y', 'Z', '-X', '-Y', '-Z')
forward_items = (
    ('X', 'X Forward', ''),
    ('Y', 'Y Forward', ''),
    ('Z', 'Z Forward', ''),
    ('-X', '-X Forward', ''),
    ('-Y', '-Y Forward', ''),
    ('-Z', '-Z Forward', ''),
)

up_items = (
    ('X', 'X Up', ''),
    ('Y', 'Y Up', ''),
    ('Z', 'Z Up', ''),
    ('-X', '-X Up', ''),
    ('-Y', '-Y Up', ''),
    ('-Z', '-Z Up', ''),
)


def forward_axis_update(self, __context):
    if self.forward_axis == self.up_axis:
        # Automatically set the up axis to the next available axis
        self.up_axis = next((axis for axis in axis_identifiers if axis != self.forward_axis), 'Z')


def up_axis_update(self, __context):
    if self.up_axis == self.forward_axis:
        # Automatically set the forward axis to the next available axis
        self.forward_axis = next((axis for axis in axis_identifiers if axis != self.up_axis), 'X')


class ForwardUpAxisMixin:
    forward_axis: EnumProperty(
        name='Forward',
        items=forward_items,
        default='X',
        update=forward_axis_update
    )
    up_axis: EnumProperty(
        name='Up',
        items=up_items,
        default='Z',
        update=up_axis_update
    )


export_space_items = [
    ('WORLD', 'World', 'Export in world space'),
    ('ARMATURE', 'Armature', 'Export the local space of the armature object'),
    ('ROOT', 'Root', 'Export in the space of the root bone')
]


class ExportSpaceMixin:
    export_space: EnumProperty(
        name='Export Space',
        items=export_space_items,
        default='WORLD'
    )
 
 
class PsxBoneExportMixin:
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        options=set(),
        description='',
        items=bone_filter_mode_items,
    )
    bone_collection_list: CollectionProperty(type=PSX_PG_bone_collection_list_item)
    bone_collection_list_index: IntProperty(default=0, name='', description='')
    root_bone_name: StringProperty(
        name='Root Bone Name',
        description='The name of the root bone when exporting a PSK with either no armature or multiple armatures',
        default='ROOT',
    )


classes = (
    PSX_PG_action_export,
    PSX_PG_bone_collection_list_item,
    PSX_UL_bone_collection_list,
    PSX_PT_action,
)
