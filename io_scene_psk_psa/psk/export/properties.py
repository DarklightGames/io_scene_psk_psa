from bpy.props import EnumProperty, CollectionProperty, IntProperty, PointerProperty, FloatProperty, StringProperty, \
    BoolProperty
from bpy.types import PropertyGroup, Material

from ...shared.data import bone_filter_mode_items
from ...shared.types import PSX_PG_bone_collection_list_item

empty_set = set()

object_eval_state_items = (
    ('EVALUATED', 'Evaluated', 'Use data from fully evaluated object'),
    ('ORIGINAL', 'Original', 'Use data from original object with no modifiers applied'),
)

export_space_items = [
    ('WORLD', 'World', 'Export in world space'),
    ('ARMATURE', 'Armature', 'Export in armature space'),
]


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

class PSK_PG_material_list_item(PropertyGroup):
    material: PointerProperty(type=Material)
    index: IntProperty()

class PSK_PG_material_name_list_item(PropertyGroup):
    material_name: StringProperty()
    index: IntProperty()




def forward_axis_update(self, _context):
    if self.forward_axis == self.up_axis:
        # Automatically set the up axis to the next available axis
        self.up_axis = next((axis for axis in axis_identifiers if axis != self.forward_axis), 'Z')


def up_axis_update(self, _context):
    if self.up_axis == self.forward_axis:
        # Automatically set the forward axis to the next available axis
        self.forward_axis = next((axis for axis in axis_identifiers if axis != self.up_axis), 'X')


class PskExportMixin:
    object_eval_state: EnumProperty(
        items=object_eval_state_items,
        name='Object Evaluation State',
        default='EVALUATED'
    )
    should_exclude_hidden_meshes: BoolProperty(
        default=False,
        name='Visible Only',
        description='Export only visible meshes'
    )
    scale: FloatProperty(
        name='Scale',
        default=1.0,
        description='Scale factor to apply to the exported mesh and armature',
        min=0.0001,
        soft_max=100.0
    )
    export_space: EnumProperty(
        name='Export Space',
        description='Space to export the mesh in',
        items=export_space_items,
        default='WORLD'
    )
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        options=empty_set,
        description='',
        items=bone_filter_mode_items,
    )
    bone_collection_list: CollectionProperty(type=PSX_PG_bone_collection_list_item)
    bone_collection_list_index: IntProperty(default=0)
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
    material_name_list: CollectionProperty(type=PSK_PG_material_name_list_item)
    material_name_list_index: IntProperty(default=0)


class PSK_PG_export(PropertyGroup, PskExportMixin):
    pass


classes = (
    PSK_PG_material_list_item,
    PSK_PG_material_name_list_item,
    PSK_PG_export,
)
