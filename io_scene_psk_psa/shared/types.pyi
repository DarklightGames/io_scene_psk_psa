from typing import Generic, TypeVar, Iterable, Sized

T = TypeVar("T")

# https://docs.blender.org/api/current/bpy.types.bpy_prop_collection_idprop.html#bpy.types.bpy_prop_collection_idprop
class BpyCollectionProperty(Generic[T], Iterable[T], Sized):
    def add(self) -> T:
        pass

    def clear(self) -> None:
        pass

    def move(self, src_index: int, dst_index: int):
        pass

    def remove(self, index: int):
        pass


class PSX_PG_bone_collection_list_item:
    armature_object_name: str
    armature_data_name: str
    name: str
    index: int
    count: int
    is_selected: bool


class PSX_PG_action_export:
    group: str
    compression_ratio: float
    key_quota: int
    fps: float


class AxisMixin:
    forward_axis: str
    up_axis: str


class TransformMixin(AxisMixin):
    scale: float


class ExportSpaceMixin:
    export_space: str


class TransformSourceMixin:
    transform_source: str


class PsxBoneExportMixin:
    bone_filter_mode: str
    bone_collection_list: BpyCollectionProperty[PSX_PG_bone_collection_list_item]
    bone_collection_list_index: int
    root_bone_name: str


class PSX_PG_scene_export(TransformSourceMixin):
    pass

bone_filter_mode_items: tuple[tuple[str, str, str]]
