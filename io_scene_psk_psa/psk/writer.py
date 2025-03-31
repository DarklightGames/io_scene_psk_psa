import os
from ctypes import Structure, sizeof
from typing import Type

from .data import Psk
from ..shared.data import PsxBone, Section, Vector3

MAX_WEDGE_COUNT = 65536
MAX_POINT_COUNT = 4294967296
MAX_BONE_COUNT = 2147483647
MAX_MATERIAL_COUNT = 256


def _write_section(fp, name: bytes, data_type: Type[Structure] = None, data: list = None):
    section = Section()
    section.name = name
    if data_type is not None and data is not None:
        section.data_size = sizeof(data_type)
        section.data_count = len(data)
    fp.write(section)
    if data is not None:
        for datum in data:
            fp.write(datum)


def write_psk(psk: Psk, path: str):
    if len(psk.wedges) > MAX_WEDGE_COUNT:
        raise RuntimeError(f'Number of wedges ({len(psk.wedges)}) exceeds limit of {MAX_WEDGE_COUNT}')
    if len(psk.points) > MAX_POINT_COUNT:
        raise RuntimeError(f'Numbers of vertices ({len(psk.points)}) exceeds limit of {MAX_POINT_COUNT}')
    if len(psk.materials) > MAX_MATERIAL_COUNT:
        raise RuntimeError(f'Number of materials ({len(psk.materials)}) exceeds limit of {MAX_MATERIAL_COUNT}')
    if len(psk.bones) > MAX_BONE_COUNT:
        raise RuntimeError(f'Number of bones ({len(psk.bones)}) exceeds limit of {MAX_BONE_COUNT}')
    if len(psk.bones) == 0:
        raise RuntimeError(f'At least one bone must be marked for export')

    # Make the directory for the file if it doesn't exist.
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        with open(path, 'wb') as fp:
            _write_section(fp, b'ACTRHEAD')
            _write_section(fp, b'PNTS0000', Vector3, psk.points)

            wedges = []
            for index, w in enumerate(psk.wedges):
                wedge = Psk.Wedge16()
                wedge.material_index = w.material_index
                wedge.u = w.u
                wedge.v = w.v
                wedge.point_index = w.point_index
                wedges.append(wedge)

            _write_section(fp, b'VTXW0000', Psk.Wedge16, wedges)
            _write_section(fp, b'FACE0000', Psk.Face, psk.faces)
            _write_section(fp, b'MATT0000', Psk.Material, psk.materials)
            _write_section(fp, b'REFSKELT', PsxBone, psk.bones)
            _write_section(fp, b'RAWWEIGHTS', Psk.Weight, psk.weights)
    except PermissionError as e:
        raise RuntimeError(f'The current user "{os.getlogin()}" does not have permission to write to "{path}"') from e
