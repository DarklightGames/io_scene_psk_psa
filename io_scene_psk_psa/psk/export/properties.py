from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Material, PropertyGroup
from ...shared.types import ExportSpaceMixin, TransformMixin, PsxBoneExportMixin

object_eval_state_items = (
    ('EVALUATED', 'Evaluated', 'Use data from fully evaluated object'),
    ('ORIGINAL', 'Original', 'Use data from original object with no modifiers applied'),
)

material_order_mode_items = (
    ('AUTOMATIC', 'Automatic', 'Automatically order the materials'),
    ('MANUAL', 'Manual', 'Manually arrange the materials'),
)

transform_source_items = (
    ('SCENE', 'Scene', 'Use the scene transform settings'),
    ('CUSTOM', 'Custom', 'Use custom transform settings'),
)

class PSK_PG_material_list_item(PropertyGroup):
    material: PointerProperty(type=Material)
    index: IntProperty()


class PSK_PG_material_name_list_item(PropertyGroup):
    material_name: StringProperty()
    index: IntProperty()


class PskExportMixin(ExportSpaceMixin, TransformMixin, PsxBoneExportMixin):
    object_eval_state: EnumProperty(
        items=object_eval_state_items,
        name='Object Evaluation State',
        default='EVALUATED'
    )
    material_order_mode: EnumProperty(
        name='Material Order',
        description='The order in which to export the materials',
        items=material_order_mode_items,
        default='AUTOMATIC'
    )
    material_name_list: CollectionProperty(type=PSK_PG_material_name_list_item)
    material_name_list_index: IntProperty(default=0)
    should_export_vertex_normals: BoolProperty(
        'Export Vertex Normals',
        default=False,
        description='Export VTXNORMS section.'
    )
    transform_source: EnumProperty(
        items=transform_source_items,
        name='Transform Source',
        default='SCENE'
    )


class PSK_PG_export(PropertyGroup, PskExportMixin):
    pass


classes = (
    PSK_PG_material_list_item,
    PSK_PG_material_name_list_item,
    PSK_PG_export,
)
