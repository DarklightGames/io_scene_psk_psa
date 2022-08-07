import ctypes

from .data import *


def _read_types(fp, data_class, section: Section, data):
    buffer_length = section.data_size * section.data_count
    buffer = fp.read(buffer_length)
    offset = 0
    for _ in range(section.data_count):
        data.append(data_class.from_buffer_copy(buffer, offset))
        offset += section.data_size


def read_psk(path) -> Psk:
    psk = Psk()
    with open(path, 'rb') as fp:
        while fp.read(1):
            fp.seek(-1, 1)
            section = Section.from_buffer_copy(fp.read(ctypes.sizeof(Section)))
            if section.name == b'ACTRHEAD':
                pass
            elif section.name == b'PNTS0000':
                _read_types(fp, Vector3, section, psk.points)
            elif section.name == b'VTXW0000':
                if section.data_size == ctypes.sizeof(Psk.Wedge16):
                    _read_types(fp, Psk.Wedge16, section, psk.wedges)
                elif section.data_size == ctypes.sizeof(Psk.Wedge32):
                    _read_types(fp, Psk.Wedge32, section, psk.wedges)
                else:
                    raise RuntimeError('Unrecognized wedge format')
            elif section.name == b'FACE0000':
                _read_types(fp, Psk.Face, section, psk.faces)
            elif section.name == b'MATT0000':
                _read_types(fp, Psk.Material, section, psk.materials)
            elif section.name == b'REFSKELT':
                _read_types(fp, Psk.Bone, section, psk.bones)
            elif section.name == b'RAWWEIGHTS':
                _read_types(fp, Psk.Weight, section, psk.weights)
            elif section.name == b'FACE3200':
                _read_types(fp, Psk.Face32, section, psk.faces)
            elif section.name == b'VERTEXCOLOR':
                _read_types(fp, Color, section, psk.vertex_colors)
            elif section.name.startswith(b'EXTRAUVS'):
                _read_types(fp, Vector2, section, psk.extra_uvs)
            elif section.name == b'VTXNORMS':
                _read_types(fp, Vector3, section, psk.vertex_normals)
            else:
                raise RuntimeError(f'Unrecognized section "{section.name} at position {15:fp.tell()}"')
    return psk
