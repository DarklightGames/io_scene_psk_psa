import ctypes

import numpy as np

from .data import *


class PsaReader(object):
    """
    This class reads the sequences and bone information immediately upon instantiation and holds onto a file handle.
    The keyframe data is not read into memory upon instantiation due to it's potentially very large size.
    To read the key data for a particular sequence, call `read_sequence_keys`.
    """

    def __init__(self, path):
        self.keys_data_offset: int = 0
        self.fp = open(path, 'rb')
        self.psa: Psa = self._read(self.fp)

    @property
    def bones(self):
        return self.psa.bones

    @property
    def sequences(self) -> OrderedDict[Psa.Sequence]:
        return self.psa.sequences

    def read_sequence_data_matrix(self, sequence_name: str):
        sequence = self.psa.sequences[sequence_name]
        keys = self.read_sequence_keys(sequence_name)
        bone_count = len(self.bones)
        matrix_size = sequence.frame_count, bone_count, 7
        matrix = np.zeros(matrix_size)
        keys_iter = iter(keys)
        for frame_index in range(sequence.frame_count):
            for bone_index in range(bone_count):
                matrix[frame_index, bone_index, :] = list(next(keys_iter).data)
        return matrix

    def read_sequence_keys(self, sequence_name: str) -> List[Psa.Key]:
        """ Reads and returns the key data for a sequence.

        :param sequence_name: The name of the sequence.
        :return: A list of Psa.Keys.
        """
        # Set the file reader to the beginning of the keys data
        sequence = self.psa.sequences[sequence_name]
        data_size = sizeof(Psa.Key)
        bone_count = len(self.psa.bones)
        buffer_length = data_size * bone_count * sequence.frame_count
        sequence_keys_offset = self.keys_data_offset + (sequence.frame_start_index * bone_count * data_size)
        self.fp.seek(sequence_keys_offset, 0)
        buffer = self.fp.read(buffer_length)
        offset = 0
        keys = []
        for _ in range(sequence.frame_count * bone_count):
            key = Psa.Key.from_buffer_copy(buffer, offset)
            keys.append(key)
            offset += data_size
        return keys

    @staticmethod
    def _read_types(fp, data_class: ctypes.Structure, section: Section, data):
        buffer_length = section.data_size * section.data_count
        buffer = fp.read(buffer_length)
        offset = 0
        for _ in range(section.data_count):
            data.append(data_class.from_buffer_copy(buffer, offset))
            offset += section.data_size

    def _read(self, fp) -> Psa:
        psa = Psa()
        while fp.read(1):
            fp.seek(-1, 1)
            section = Section.from_buffer_copy(fp.read(ctypes.sizeof(Section)))
            if section.name == b'ANIMHEAD':
                pass
            elif section.name == b'BONENAMES':
                PsaReader._read_types(fp, Psa.Bone, section, psa.bones)
            elif section.name == b'ANIMINFO':
                sequences = []
                PsaReader._read_types(fp, Psa.Sequence, section, sequences)
                for sequence in sequences:
                    psa.sequences[sequence.name.decode()] = sequence
            elif section.name == b'ANIMKEYS':
                # Skip keys on this pass. We will keep this file open and read from it as needed.
                self.keys_data_offset = fp.tell()
                fp.seek(section.data_size * section.data_count, 1)
            elif section.name in [b'SCALEKEYS']:
                fp.seek(section.data_size * section.data_count, 1)
            else:
                raise RuntimeError(f'Unrecognized section "{section.name}"')
        return psa
