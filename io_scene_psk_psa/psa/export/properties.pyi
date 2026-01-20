from bpy.types import PropertyGroup, Object, Action

from ...shared.types import BpyCollectionProperty, TransformMixin, ExportSpaceMixin, PsxBoneExportMixin, TransformSourceMixin

class PsaExportSequenceMixin(PropertyGroup):
    name: str
    is_selected: bool
    frame_start: int
    frame_end: int
    group: str
    action_name: str
    armature_object_name: str
    marker_index: int
    is_pose_marker: bool

    @property
    def action(self) -> Action | None: ...

    @property
    def armature_object(self) -> Object | None: ...

    @property
    def is_reversed(self) -> bool: ...


class PSA_PG_export_sequence(PsaExportSequenceMixin):
    """Concrete type for PSA export sequences."""
    pass


class PsaExportMixin(PropertyGroup, TransformMixin, ExportSpaceMixin, PsxBoneExportMixin, TransformSourceMixin):
    sequence_source: str
    nla_track: str
    nla_track_index: int
    fps_source: str
    fps_custom: float
    compression_ratio_source: str
    compression_ratio_custom: float
    action_list: BpyCollectionProperty[PSA_PG_export_sequence]
    action_list_index: int
    marker_list: BpyCollectionProperty[PSA_PG_export_sequence]
    marker_list_index: int
    nla_strip_list: BpyCollectionProperty[PSA_PG_export_sequence]
    nla_strip_list_index: int
    active_action_list: BpyCollectionProperty[PSA_PG_export_sequence]
    active_action_list_index: int
    sequence_name_prefix: str
    sequence_name_suffix: str
    sequence_filter_name: str
    sequence_use_filter_invert: bool
    sequence_filter_asset: bool
    sequence_filter_pose_marker: bool
    sequence_use_filter_sort_reverse: bool
    sequence_filter_reversed: bool
    sampling_mode: str
    group_source: str
    group_custom: str


class PSA_PG_export(PsaExportMixin):
    pass


def get_sequences_from_name_and_frame_range(name: str, frame_start: int, frame_end: int):
    pass

def filter_sequences(pg: PsaExportMixin, sequences) -> list[int]:
    pass
