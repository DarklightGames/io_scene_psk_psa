from ctypes import Structure, sizeof
from typing import Type

import bpy.app.translations

from .data import Psk
from ..data import Section, Vector3

MAX_WEDGE_COUNT = 65536
MAX_POINT_COUNT = 4294967296
MAX_BONE_COUNT = 256
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
        message = bpy.app.translations.pgettext_iface('Number of wedges ({wedge_count}) exceeds limit of {MAX_WEDGE_COUNT}')
        raise RuntimeError(message.format(wedge_count=len(psk.wedges), MAX_WEDGE_COUNT=MAX_WEDGE_COUNT))
    if len(psk.points) > MAX_POINT_COUNT:
        message = bpy.app.translations.pgettext_iface('Numbers of vertices ({point_count}) exceeds limit of {MAX_POINT_COUNT}')
        raise RuntimeError(message.format(point_count=len(psk.points), MAX_POINT_COUNT=MAX_POINT_COUNT))
    if len(psk.materials) > MAX_MATERIAL_COUNT:
        message = bpy.app.translations.pgettext_iface('Number of materials ({material_count}) exceeds limit of {MAX_MATERIAL_COUNT}')
        raise RuntimeError(message.format(material_count=len(psk.materials), MAX_MATERIAL_COUNT=MAX_MATERIAL_COUNT))
    if len(psk.bones) > MAX_BONE_COUNT:
        message = bpy.app.translations.pgettext_iface('Number of bones ({bone_count}) exceeds limit of {MAX_BONE_COUNT}')
        raise RuntimeError(message.format(bone_count=len(psk.bones), MAX_BONE_COUNT=MAX_BONE_COUNT))
    elif len(psk.bones) == 0:
        message = bpy.app.translations.pgettext_iface('At least one bone must be marked for export')
        raise RuntimeError(message)

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
        _write_section(fp, b'REFSKELT', Psk.Bone, psk.bones)
        _write_section(fp, b'RAWWEIGHTS', Psk.Weight, psk.weights)
