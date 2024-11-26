from bpy.props import EnumProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty, FloatProperty
from bpy.types import PropertyGroup, Material

from ...shared.types import PSX_PG_bone_collection_list_item

empty_set = set()


object_eval_state_items = (
    ('EVALUATED', 'Evaluated', 'Use data from fully evaluated object'),
    ('ORIGINAL', 'Original', 'Use data from original object with no modifiers applied'),
)

class PSK_PG_material_list_item(PropertyGroup):
    material: PointerProperty(type=Material)
    index: IntProperty()


class PSK_PG_export(PropertyGroup):
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        options=empty_set,
        description='',
        items=(
            ('ALL', 'All', 'All bones will be exported'),
            ('BONE_COLLECTIONS', 'Bone Collections',
             'Only bones belonging to the selected bone collections and their ancestors will be exported')
        )
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
    should_enforce_bone_name_restrictions: BoolProperty(
        default=False,
        name='Enforce Bone Name Restrictions',
        description='Enforce that bone names must only contain letters, numbers, spaces, hyphens and underscores.\n\n'
                    'Depending on the engine, improper bone names might not be referenced correctly by scripts'
    )
    scale: FloatProperty(
        name='Scale',
        default=1.0,
        description='Scale factor to apply to the exported mesh',
        min=0.0001,
        soft_max=100.0
    )


classes = (
    PSK_PG_material_list_item,
    PSK_PG_export,
)
