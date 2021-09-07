from .data import *
from typing import AnyStr
import ctypes


class PsaReader(object):

    def __init__(self):
        pass

    @staticmethod
    def read_types(fp, data_class: ctypes.Structure, section: Section, data):
        buffer_length = section.data_size * section.data_count
        buffer = fp.read(buffer_length)
        offset = 0
        for _ in range(section.data_count):
            data.append(data_class.from_buffer_copy(buffer, offset))
            offset += section.data_size

    def scan_sequence_names(self, path) -> List[AnyStr]:
        sequences = []
        with open(path, 'rb') as fp:
            if fp.read(8) != b'ANIMINFO':
                raise IOError('Unexpected file format')
            fp.seek(0, 0)
            while fp.read(1):
                fp.seek(-1, 1)
                section = Section.from_buffer_copy(fp.read(ctypes.sizeof(Section)))
                if section.name == b'ANIMINFO':
                    PsaReader.read_types(fp, Psa.Sequence, section, sequences)
                    return [sequence.name for sequence in sequences]
                else:
                    fp.seek(section.data_size * section.data_count, 1)
        return []

    def read(self, path) -> Psa:
        psa = Psa()
        with open(path, 'rb') as fp:
            while fp.read(1):
                fp.seek(-1, 1)
                section = Section.from_buffer_copy(fp.read(ctypes.sizeof(Section)))
                if section.name == b'ANIMHEAD':
                    pass
                elif section.name == b'BONENAMES':
                    PsaReader.read_types(fp, Psa.Bone, section, psa.bones)
                elif section.name == b'ANIMINFO':
                    PsaReader.read_types(fp, Psa.Sequence, section, psa.sequences)
                elif section.name == b'ANIMKEYS':
                    PsaReader.read_types(fp, Psa.Key, section, psa.keys)
                else:
                    raise RuntimeError(f'Unrecognized section "{section.name}"')
        return psa
1