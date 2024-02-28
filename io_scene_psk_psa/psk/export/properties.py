from bpy.props import EnumProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty
from bpy.types import PropertyGroup, Material

from ...types import PSX_PG_bone_collection_list_item


class PSK_PG_material_list_item(PropertyGroup):
    material: PointerProperty(type=Material)
    index: IntProperty()


class PSK_PG_export(PropertyGroup):
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        options=set(),
        description='',
        items=(
            ('ALL', 'All', 'All bones will be exported'),
            ('BONE_COLLECTIONS', 'Bone Collections',
             'Only bones belonging to the selected bone collections and their ancestors will be exported')
        )
    )
    bone_collection_list: CollectionProperty(type=PSX_PG_bone_collection_list_item)
    bone_collection_list_index: IntProperty(default=0)
    use_raw_mesh_data: BoolProperty(default=False, name='Raw Mesh Data', description='No modifiers will be evaluated as part of the exported mesh')
    material_list: CollectionProperty(type=PSK_PG_material_list_item)
    material_list_index: IntProperty(default=0)
    should_enforce_bone_name_restrictions: BoolProperty(
        default=False,
        name='Enforce Bone Name Restrictions',
        description='Enforce that bone names must only contain letters, numbers, spaces, hyphens and underscores.\n\n'
                    'Depending on the engine, improper bone names might not be referenced correctly by scripts'
    )


classes = (
    PSK_PG_material_list_item,
    PSK_PG_export,
)
