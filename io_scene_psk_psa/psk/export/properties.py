from bpy.props import EnumProperty, CollectionProperty, IntProperty, PointerProperty, FloatProperty
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

class PSK_PG_material_list_item(PropertyGroup):
    material: PointerProperty(type=Material)
    index: IntProperty()


class PSK_PG_export(PropertyGroup):
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        options=empty_set,
        description='',
        items=bone_filter_mode_items
    )
    bone_collection_list: CollectionProperty(type=PSX_PG_bone_collection_list_item)
    bone_collection_list_index: IntProperty(default=0)
    object_eval_state: EnumProperty(
        items=object_eval_state_items,
        name='Object Evaluation State',
        default='EVALUATED'
    )
    material_list: CollectionProperty(type=PSK_PG_material_list_item)
    material_list_index: IntProperty(default=0)
    scale: FloatProperty(
        name='Scale',
        default=1.0,
        description='Scale factor to apply to the exported mesh',
        min=0.0001,
        soft_max=100.0
    )
    export_space: EnumProperty(
        name='Export Space',
        options=empty_set,
        description='Space to export the mesh in',
        items=export_space_items,
        default='WORLD'
    )


classes = (
    PSK_PG_material_list_item,
    PSK_PG_export,
)
