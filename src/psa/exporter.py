from typing import Type
from .data import *


class PsaExporter(object):
    def __init__(self, psa: Psa):
        self.psa: Psa = psa

    # This method is shared by both PSA/K file formats, move this?
    @staticmethod
    def write_section(fp, name: bytes, data_type: Type[Structure] = None, data: list = None):
        section = Section()
        section.name = name
        if data_type is not None and data is not None:
            section.data_size = sizeof(data_type)
            section.data_count = len(data)
        fp.write(section)
        if data is not None:
            for datum in data:
                fp.write(datum)

    def export(self, path: str):
        with open(path, 'wb') as fp:
            self.write_section(fp, b'ANIMHEAD')
            self.write_section(fp, b'BONENAMES', Psa.Bone, self.psa.bones)
            self.write_section(fp, b'ANIMINFO', Psa.Sequence, self.psa.sequences)
            self.write_section(fp, b'ANIMKEYS', Psa.Key, self.psa.keys)
