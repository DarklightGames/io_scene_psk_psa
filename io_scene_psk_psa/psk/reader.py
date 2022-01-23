from .data import *
import ctypes


class PskReader(object):

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

    def read(self, path) -> Psk:
        psk = Psk()
        with open(path, 'rb') as fp:
            while fp.read(1):
                fp.seek(-1, 1)
                section = Section.from_buffer_copy(fp.read(ctypes.sizeof(Section)))
                if section.name == b'ACTRHEAD':
                    pass
                elif section.name == b'PNTS0000':
                    PskReader.read_types(fp, Vector3, section, psk.points)
                elif section.name == b'VTXW0000':
                    if section.data_size == ctypes.sizeof(Psk.Wedge16):
                        PskReader.read_types(fp, Psk.Wedge16, section, psk.wedges)
                    elif section.data_size == ctypes.sizeof(Psk.Wedge32):
                        PskReader.read_types(fp, Psk.Wedge32, section, psk.wedges)
                    else:
                        raise RuntimeError('Unrecognized wedge format')
                elif section.name == b'FACE0000':
                    PskReader.read_types(fp, Psk.Face, section, psk.faces)
                elif section.name == b'MATT0000':
                    PskReader.read_types(fp, Psk.Material, section, psk.materials)
                elif section.name == b'REFSKELT':
                    PskReader.read_types(fp, Psk.Bone, section, psk.bones)
                elif section.name == b'RAWWEIGHTS':
                    PskReader.read_types(fp, Psk.Weight, section, psk.weights)
                else:
                    raise RuntimeError(f'Unrecognized section "{section.name}"')
        return psk
