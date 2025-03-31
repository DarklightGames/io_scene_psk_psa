import ctypes
import os
import re
import warnings
from pathlib import Path
from typing import List
from ..shared.data import Section
from .data import Color, Psk, PsxBone, Vector2, Vector3


def _read_types(fp, data_class, section: Section, data):
    buffer_length = section.data_size * section.data_count
    buffer = fp.read(buffer_length)
    offset = 0
    for _ in range(section.data_count):
        data.append(data_class.from_buffer_copy(buffer, offset))
        offset += section.data_size


def _read_material_references(path: str) -> List[str]:
    property_file_path = Path(path).with_suffix('.props.txt')
    if not property_file_path.is_file():
        # Property file does not exist.
        return []
    # Do a crude regex match to find the Material list entries.
    contents = property_file_path.read_text()
    pattern = r'Material\s*=\s*([^\s^,]+)'
    return re.findall(pattern, contents)


def read_psk(path: str) -> Psk:
    psk = Psk()

    # Read the PSK file sections.
    with open(path, 'rb') as fp:
        while fp.read(1):
            fp.seek(-1, 1)
            section = Section.from_buffer_copy(fp.read(ctypes.sizeof(Section)))
            match section.name:
                case b'ACTRHEAD':
                    pass
                case b'PNTS0000':
                    _read_types(fp, Vector3, section, psk.points)
                case b'VTXW0000':
                    if section.data_size == ctypes.sizeof(Psk.Wedge16):
                        _read_types(fp, Psk.Wedge16, section, psk.wedges)
                    elif section.data_size == ctypes.sizeof(Psk.Wedge32):
                        _read_types(fp, Psk.Wedge32, section, psk.wedges)
                    else:
                        raise RuntimeError('Unrecognized wedge format')
                case b'FACE0000':
                    _read_types(fp, Psk.Face, section, psk.faces)
                case b'MATT0000':
                    _read_types(fp, Psk.Material, section, psk.materials)
                case b'REFSKELT':
                    _read_types(fp, PsxBone, section, psk.bones)
                case b'RAWWEIGHTS':
                    _read_types(fp, Psk.Weight, section, psk.weights)
                case b'FACE3200':
                    _read_types(fp, Psk.Face32, section, psk.faces)
                case b'VERTEXCOLOR':
                    _read_types(fp, Color, section, psk.vertex_colors)
                case b'VTXNORMS':
                    _read_types(fp, Vector3, section, psk.vertex_normals)
                case b'MRPHINFO':
                    _read_types(fp, Psk.MorphInfo, section, psk.morph_infos)
                case b'MRPHDATA':
                    _read_types(fp, Psk.MorphData, section, psk.morph_data)
                case _:
                    if section.name.startswith(b'EXTRAUVS'):
                        _read_types(fp, Vector2, section, psk.extra_uvs)
                    else:
                        # Section is not handled, skip it.
                        fp.seek(section.data_size * section.data_count, os.SEEK_CUR)
                        warnings.warn(f'Unrecognized section "{section.name} at position {fp.tell():15}"')

    """
    UEViewer exports a sidecar file (*.props.txt) with fully-qualified reference paths for each material
    (e.g., Texture'Package.Group.Object').
    """
    psk.material_references = _read_material_references(path)

    """
    Tools like UEViewer and CUE4Parse write the point index as a 32-bit integer, exploiting the fact that due to struct
    alignment, there were 16-bits of padding following the original 16-bit point index in the wedge struct.
    However, this breaks compatibility with PSK files that were created with older tools that treated the
    point index as a 16-bit integer and might have junk data written to the padding bits.
    To work around this, we check if each point is still addressable using a 16-bit index, and if it is, assume the
    point index is a 16-bit integer and truncate the high bits.
    """
    if len(psk.points) <= 65536:
        for wedge in psk.wedges:
            wedge.point_index &= 0xFFFF

    return psk
