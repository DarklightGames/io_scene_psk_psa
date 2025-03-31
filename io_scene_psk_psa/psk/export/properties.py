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
from ...shared.types import ExportSpaceMixin, ForwardUpAxisMixin, PsxBoneExportMixin

object_eval_state_items = (
    ('EVALUATED', 'Evaluated', 'Use data from fully evaluated object'),
    ('ORIGINAL', 'Original', 'Use data from original object with no modifiers applied'),
)

material_order_mode_items = (
    ('AUTOMATIC', 'Automatic', 'Automatically order the materials'),
    ('MANUAL', 'Manual', 'Manually arrange the materials'),
)

class PSK_PG_material_list_item(PropertyGroup):
    material: PointerProperty(type=Material)
    index: IntProperty()

class PSK_PG_material_name_list_item(PropertyGroup):
    material_name: StringProperty()
    index: IntProperty()


class PskExportMixin(ExportSpaceMixin, ForwardUpAxisMixin, PsxBoneExportMixin):
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
    material_order_mode: EnumProperty(
        name='Material Order',
        description='The order in which to export the materials',
        items=material_order_mode_items,
        default='AUTOMATIC'
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
