import re
from configparser import ConfigParser
from typing import Dict, List

REMOVE_TRACK_LOCATION = (1 << 0)
REMOVE_TRACK_ROTATION = (1 << 1)


class PsaConfig:
    def __init__(self):
        self.sequence_bone_flags: Dict[str, Dict[int, int]] = dict()


def _load_config_file(file_path: str) -> ConfigParser:
    """
    UEViewer exports a dialect of INI files that is not compatible with Python's ConfigParser.
    Specifically, it allows values in this format:

    [Section]
    Key1
    Key2

    This is not allowed in Python's ConfigParser, which requires a '=' character after each key name.
    To work around this, we'll modify the file to add the '=' character after each key name if it is missing.
    """
    with open(file_path, 'r') as f:
        lines = f.read().split('\n')

    lines = [re.sub(r'^\s*([^=]+)\s*$', r'\1=', line) for line in lines]

    contents = '\n'.join(lines)

    config = ConfigParser()
    config.read_string(contents)

    return config


def _get_bone_flags_from_value(value: str) -> int:
    match value:
        case 'all':
            return REMOVE_TRACK_LOCATION | REMOVE_TRACK_ROTATION
        case 'trans':
            return REMOVE_TRACK_LOCATION
        case 'rot':
            return REMOVE_TRACK_ROTATION
        case _:
            return 0


def read_psa_config(psa_sequence_names: List[str], file_path: str) -> PsaConfig:
    psa_config = PsaConfig()

    config = _load_config_file(file_path)

    if config.has_section('RemoveTracks'):
        for key, value in config.items('RemoveTracks'):
            match = re.match(f'^(.+)\.(\d+)$', key)
            sequence_name = match.group(1)

            # Map the sequence name onto the actual sequence name in the PSA file.
            try:
                lowercase_sequence_names = [sequence_name.lower() for sequence_name in psa_sequence_names]
                sequence_name = psa_sequence_names[lowercase_sequence_names.index(sequence_name.lower())]
            except ValueError:
                # Sequence name is not in the PSA file.
                continue

            if sequence_name not in psa_config.sequence_bone_flags:
                psa_config.sequence_bone_flags[sequence_name] = dict()

            bone_index = int(match.group(2))
            psa_config.sequence_bone_flags[sequence_name][bone_index] = _get_bone_flags_from_value(value)

    return psa_config
