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
from ...psk.properties import vertex_color_space_items

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
    def is_extended_data_export_enabled(self):
        return self.should_export_vertex_normals or self.should_export_extra_uvs or self.should_export_vertex_colors or self.should_export_shape_keys
    def update_extended_data_property(self, context):
        if (context.active_operator is not None):
            if self.is_extended_data_export_enabled():
                context.active_operator.filename_ext = '.pskx'
            else:
                context.active_operator.filename_ext = '.psk'
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
    transform_source: EnumProperty(
        items=transform_source_items,
        name='Transform Source',
        default='SCENE'
    )
    should_export_vertex_normals: BoolProperty(
        name='Export Vertex Normals',
        default=False,
        description='Export VTXNORMS section.\n\nThis will export as a PSKX file',
        update=update_extended_data_property
    )
    should_export_shape_keys: BoolProperty(
        default=False,
        name='Export Shape Keys',
        description='Export MRPHINFO and MRPHDATA sections.\n\nThis will export as a PSKX file',
        update=update_extended_data_property
    )
    should_export_extra_uvs: BoolProperty(
        default=False,
        name='Export Extra UVs',
        description='Export EXTRAUVS section.\n\nThis will export as a PSKX file',
        update=update_extended_data_property
    )
    should_export_vertex_colors: BoolProperty(
        default=False,
        name='Export Vertex Colors',
        description='Export VERTEXCOLOR section.\n\nThis will export as a PSKX file',
        update=update_extended_data_property
    )
    vertex_color_space: EnumProperty(
        name='Vertex Color Space',
        options=set(),
        description='The vertex color space',
        default='SRGBA',
        items=vertex_color_space_items
    )


class PSK_PG_export(PropertyGroup, PskExportMixin):
    pass


classes = (
    PSK_PG_material_list_item,
    PSK_PG_material_name_list_item,
    PSK_PG_export,
)
