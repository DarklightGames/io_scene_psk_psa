import re
from configparser import ConfigParser
from typing import Dict

from .reader import PsaReader

REMOVE_TRACK_LOCATION = (1 << 0)
REMOVE_TRACK_ROTATION = (1 << 1)


class PsaConfig:
    def __init__(self):
        self.sequence_bone_flags: Dict[str, Dict[int, int]] = dict()


def read_psa_config(psa_reader: PsaReader, file_path: str) -> PsaConfig:
    psa_config = PsaConfig()

    config = ConfigParser()
    config.read(file_path)

    psa_sequence_names = list(psa_reader.sequences.keys())
    lowercase_sequence_names = [sequence_name.lower() for sequence_name in psa_sequence_names]

    if config.has_section('RemoveTracks'):
        for key, value in config.items('RemoveTracks'):
            match = re.match(f'^(.+)\.(\d+)$', key)
            sequence_name = match.group(1)
            bone_index = int(match.group(2))

            # Map the sequence name onto the actual sequence name in the PSA file.
            try:
                sequence_name = psa_sequence_names[lowercase_sequence_names.index(sequence_name.lower())]
            except ValueError:
                pass

            if sequence_name not in psa_config.sequence_bone_flags:
                psa_config.sequence_bone_flags[sequence_name] = dict()

            match value:
                case 'all':
                    psa_config.sequence_bone_flags[sequence_name][bone_index] = (REMOVE_TRACK_LOCATION | REMOVE_TRACK_ROTATION)
                case 'trans':
                    psa_config.sequence_bone_flags[sequence_name][bone_index] = REMOVE_TRACK_LOCATION
                case 'rot':
                    psa_config.sequence_bone_flags[sequence_name][bone_index] = REMOVE_TRACK_ROTATION

    return psa_config
