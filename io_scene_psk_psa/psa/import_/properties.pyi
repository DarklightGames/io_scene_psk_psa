from bpy.types import PropertyGroup, Text

from ...shared.types import BpyCollectionProperty


class PSA_PG_import_action_list_item:
    action_name: str
    is_selected: bool


class PSA_PG_bone:
    bone_name: str


class PSA_PG_data(PropertyGroup):
    bones: BpyCollectionProperty[PSA_PG_bone]
    sequence_count: int

class PsaImportMixin:
    should_use_fake_user: bool
    should_use_config_file: bool
    should_stash: bool
    should_use_action_name_prefix: bool
    action_name_prefix: str
    should_overwrite: bool
    should_write_keyframes: bool
    should_write_metadata: bool
    should_write_scale_keys: bool
    sequence_filter_name: str
    sequence_filter_is_selected: bool
    sequence_use_filter_invert: bool
    sequence_use_filter_regex: bool
    should_convert_to_samples: bool
    bone_mapping_is_case_sensitive: bool
    bone_mapping_should_ignore_trailing_whitespace: bool
    fps_source: str
    fps_custom: float
    compression_ratio_source: str
    compression_ratio_custom: float
    translation_scale: float
    
class PSA_PG_import:
    psa_error: str
    psa: PSA_PG_data
    sequence_list: BpyCollectionProperty[PSA_PG_import_action_list_item]
    sequence_list_index: int
    sequence_filter_name: str
    sequence_filter_is_selected: bool
    sequence_use_filter_invert: bool
    sequence_use_filter_regex: bool
    select_text: Text | None



def filter_sequences(pg: PSA_PG_import, sequences) -> list[int]:
    pass


def get_visible_sequences(pg: PSA_PG_import, sequences) -> list[PSA_PG_import_action_list_item]:
    pass
