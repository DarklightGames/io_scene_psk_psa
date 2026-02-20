from ...shared.types import BpyCollectionProperty, ExportSpaceMixin, TransformMixin, PsxBoneExportMixin, TransformSourceMixin


class PSK_PG_material_name_list_item:
    material_name: str
    index: int


class PskExportMixin(ExportSpaceMixin, TransformMixin, PsxBoneExportMixin, TransformSourceMixin):
    object_eval_state: str
    material_order_mode: str
    material_name_list: BpyCollectionProperty[PSK_PG_material_name_list_item]
    material_name_list_index: int
    should_export_vertex_normals: bool


class PSK_PG_export(PskExportMixin):
    pass