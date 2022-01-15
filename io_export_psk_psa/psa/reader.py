from .data import *
from typing import AnyStr
import ctypes


class PsaReader(object):

    def __init__(self, path):
        self.keys_data_offset = 0
        self.fp = open(path, 'rb')
        self.psa = self._read(self.fp)

    @staticmethod
    def read_types(fp, data_class: ctypes.Structure, section: Section, data):
        buffer_length = section.data_size * section.data_count
        buffer = fp.read(buffer_length)
        offset = 0
        for _ in range(section.data_count):
            data.append(data_class.from_buffer_copy(buffer, offset))
            offset += section.data_size

    # TODO: this probably isn't actually needed anymore, we can just read it once.
    @staticmethod
    def scan_sequence_names(path) -> List[AnyStr]:
        sequences = []
        with open(path, 'rb') as fp:
            while fp.read(1):
                fp.seek(-1, 1)
                section = Section.from_buffer_copy(fp.read(ctypes.sizeof(Section)))
                if section.name == b'ANIMINFO':
                    PsaReader.read_types(fp, Psa.Sequence, section, sequences)
                    return [sequence.name for sequence in sequences]
                else:
                    fp.seek(section.data_size * section.data_count, 1)
        return []

    def get_sequence_keys(self, sequence_name) -> List[Psa.Key]:
        # Set the file reader to the beginning of the keys data
        sequence = self.psa.sequences[sequence_name]
        data_size = sizeof(Psa.Key)
        bone_count = len(self.psa.bones)
        buffer_length = data_size * bone_count * sequence.frame_count
        print(f'data_size: {data_size}')
        print(f'buffer_length: {buffer_length}')
        print(f'bone_count: {bone_count}')
        print(f'sequence.frame_count: {sequence.frame_count}')
        print(f'self.keys_data_offset: {self.keys_data_offset}')
        sequence_keys_offset = self.keys_data_offset + (sequence.frame_start_index * bone_count * data_size)
        print(f'sequence_keys_offset: {sequence_keys_offset}')
        self.fp.seek(sequence_keys_offset, 0)
        buffer = self.fp.read(buffer_length)
        offset = 0
        keys = []
        for _ in range(sequence.frame_count * bone_count):
            key = Psa.Key.from_buffer_copy(buffer, offset)
            keys.append(key)
            offset += data_size
        return keys

    def _read(self, fp) -> Psa:
        psa = Psa()
        while fp.read(1):
            fp.seek(-1, 1)
            section = Section.from_buffer_copy(fp.read(ctypes.sizeof(Section)))
            if section.name == b'ANIMHEAD':
                pass
            elif section.name == b'BONENAMES':
                PsaReader.read_types(fp, Psa.Bone, section, psa.bones)
            elif section.name == b'ANIMINFO':
                sequences = []
                PsaReader.read_types(fp, Psa.Sequence, section, sequences)
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
1