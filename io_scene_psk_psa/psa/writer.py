from ctypes import Structure, sizeof
from typing import Type

from .data import Psa
from ..shared.data import PsxBone, Section


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


def write_psa(psa: Psa, path: str):
    with open(path, 'wb') as fp:
        write_section(fp, b'ANIMHEAD')
        write_section(fp, b'BONENAMES', PsxBone, psa.bones)
        write_section(fp, b'ANIMINFO', Psa.Sequence, list(psa.sequences.values()))
        write_section(fp, b'ANIMKEYS', Psa.Key, psa.keys)
