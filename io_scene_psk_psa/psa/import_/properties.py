import re
from fnmatch import fnmatch
from typing import List

from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup, Text


class PSA_PG_import_action_list_item(PropertyGroup):
    action_name: StringProperty(options=set())
    is_selected: BoolProperty(default=True, options=set())


class PSA_PG_bone(PropertyGroup):
    bone_name: StringProperty(options=set())


class PSA_PG_data(PropertyGroup):
    bones: CollectionProperty(type=PSA_PG_bone)
    sequence_count: IntProperty(default=0)


bone_mapping_items = (
    ('EXACT', 'Exact', 'Bone names must match exactly.', 'EXACT', 0),
    ('CASE_INSENSITIVE', 'Case Insensitive', 'Bones names must match, ignoring case (e.g., the bone PSA bone \'root\' can be mapped to the armature bone \'Root\')', 'CASE_INSENSITIVE', 1),
)

fps_source_items = (
    ('SEQUENCE', 'Sequence', 'The sequence frame rate matches the original frame rate', 'ACTION', 0),
    ('SCENE', 'Scene', 'The sequence is resampled to the frame rate of the scene', 'SCENE_DATA', 1),
    ('CUSTOM', 'Custom', 'The sequence is resampled to a custom frame rate', 2),
)

compression_ratio_source_items = (
    ('ACTION', 'Action', 'The compression ratio is sourced from the action metadata', 'ACTION', 0),
    ('CUSTOM', 'Custom', 'The compression ratio is set to a custom value', 1),
)

class PsaImportMixin:
    should_use_fake_user: BoolProperty(default=True, name='Fake User',
                                       description='Assign each imported action a fake user so that the data block is '
                                                   'saved even it has no users',
                                       options=set())
    should_use_config_file: BoolProperty(default=True, name='Use Config File',
                                         description='Use the .config file that is sometimes generated when the PSA '
                                                     'file is exported from UEViewer. This file contains '
                                                     'options that can be used to filter out certain bones tracks '
                                                     'from the imported actions',
                                         options=set())
    should_stash: BoolProperty(default=False, name='Stash',
                               description='Stash each imported action as a strip on a new non-contributing NLA track',
                               options=set())
    should_use_action_name_prefix: BoolProperty(default=False, name='Prefix Action Name', options=set())
    action_name_prefix: StringProperty(default='', name='Prefix', options=set())
    should_overwrite: BoolProperty(default=False, name='Overwrite', options=set(),
                                   description='If an action with a matching name already exists, the existing action '
                                               'will have it\'s data overwritten instead of a new action being created')
    should_write_keyframes: BoolProperty(default=True, name='Keyframes', options=set())
    should_write_metadata: BoolProperty(default=True, name='Metadata', options=set(),
                                        description='Additional data will be written to the custom properties of the '
                                                    'Action (e.g., frame rate)')
    sequence_filter_name: StringProperty(default='', options={'TEXTEDIT_UPDATE'})
    sequence_filter_is_selected: BoolProperty(default=False, options=set(), name='Only Show Selected',
                                              description='Only show selected sequences')
    sequence_use_filter_invert: BoolProperty(default=False, options=set())
    sequence_use_filter_regex: BoolProperty(default=False, name='Regular Expression',
                                            description='Filter using regular expressions', options=set())

    should_convert_to_samples: BoolProperty(
        default=False,
        name='Convert to Samples',
        description='Convert keyframes to read-only samples. '
                    'Recommended if you do not plan on editing the actions directly'
    )
    bone_mapping_mode: EnumProperty(
        name='Bone Mapping',
        options=set(),
        description='The method by which bones from the incoming PSA file are mapped to the armature',
        items=bone_mapping_items,
        default='CASE_INSENSITIVE'
    )
    fps_source: EnumProperty(name='FPS Source', items=fps_source_items)
    fps_custom: FloatProperty(
        default=30.0,
        name='Custom FPS',
        description='The frame rate to which the imported sequences will be resampled to',
        options=set(),
        min=1.0,
        soft_min=1.0,
        soft_max=60.0,
        step=100,
    )
    compression_ratio_source: EnumProperty(name='Compression Ratio Source', items=compression_ratio_source_items, default='ACTION')
    compression_ratio_custom: FloatProperty(
        default=1.0,
        name='Custom Compression Ratio',
        description='The compression ratio to apply to the imported sequences',
        options=set(),
        min=0.0,
        soft_min=0.0,
        soft_max=1.0,
        step=0.0625,
    )
    translation_scale: FloatProperty(
        name='Translation Scale',
        default=1.0,
        description='Scale factor for bone translation values. Use this when the scale of the armature does not match the PSA file'
    )


# This property group lives "globally" in the scene, since Operators cannot have PointerProperty or CollectionProperty
# properties.
class PSA_PG_import(PropertyGroup):
    psa_error: StringProperty(default='')
    psa: PointerProperty(type=PSA_PG_data)
    sequence_list: CollectionProperty(type=PSA_PG_import_action_list_item)
    sequence_list_index: IntProperty(name='', default=0)
    sequence_filter_name: StringProperty(default='', options={'TEXTEDIT_UPDATE'})
    sequence_filter_is_selected: BoolProperty(default=False, options=set(), name='Only Show Selected',
                                              description='Only show selected sequences')
    sequence_use_filter_invert: BoolProperty(default=False, options=set())
    sequence_use_filter_regex: BoolProperty(default=False, name='Regular Expression',
                                            description='Filter using regular expressions', options=set())
    select_text: PointerProperty(type=Text)


def filter_sequences(pg: PSA_PG_import, sequences) -> List[int]:
    bitflag_filter_item = 1 << 30
    flt_flags = [bitflag_filter_item] * len(sequences)

    if pg.sequence_filter_name is not None:
        # Filter name is non-empty.
        if pg.sequence_use_filter_regex:
            # Use regular expression. If regex pattern doesn't compile, just ignore it.
            try:
                regex = re.compile(pg.sequence_filter_name)
                for i, sequence in enumerate(sequences):
                    if not regex.match(sequence.action_name):
                        flt_flags[i] &= ~bitflag_filter_item
            except re.error:
                pass
        else:
            # User regular text matching.
            for i, sequence in enumerate(sequences):
                if not fnmatch(sequence.action_name, f'*{pg.sequence_filter_name}*'):
                    flt_flags[i] &= ~bitflag_filter_item

    if pg.sequence_filter_is_selected:
        for i, sequence in enumerate(sequences):
            if not sequence.is_selected:
                flt_flags[i] &= ~bitflag_filter_item

    if pg.sequence_use_filter_invert:
        # Invert filter flags for all items.
        for i, sequence in enumerate(sequences):
            flt_flags[i] ^= bitflag_filter_item

    return flt_flags


def get_visible_sequences(pg: PSA_PG_import, sequences) -> List[PSA_PG_import_action_list_item]:
    bitflag_filter_item = 1 << 30
    visible_sequences = []
    for i, flag in enumerate(filter_sequences(pg, sequences)):
        if bool(flag & bitflag_filter_item):
            visible_sequences.append(sequences[i])
    return visible_sequences


classes = (
    PSA_PG_import_action_list_item,
    PSA_PG_bone,
    PSA_PG_data,
    PSA_PG_import,
)
