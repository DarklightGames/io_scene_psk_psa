from typing import Type
from .data import *


class PskExporter(object):
    def __init__(self, psk: Psk):
        self.psk: Psk = psk

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
        # TODO: add logic somewhere to assert lengths of ctype structs
        with open(path, 'wb') as fp:
            self.write_section(fp, b'ACTRHEAD')
            self.write_section(fp, b'PNTS0000', Vector3, self.psk.points)

            # WEDGES
            # TODO: this really should be on the level of the builder, not the exporter
            if len(self.psk.wedges) <= 65536:
                wedge_type = Psk.Wedge16
            else:
                wedge_type = Psk.Wedge32

            self.write_section(fp, b'VTXW0000', wedge_type, self.psk.wedges)
            self.write_section(fp, b'FACE0000', Psk.Face, self.psk.faces)
            self.write_section(fp, b'MATT0000', Psk.Material, self.psk.materials)
            self.write_section(fp, b'REFSKELT', Psk.Bone, self.psk.bones)
            self.write_section(fp, b'RAWWEIGHTS', Psk.Weight, self.psk.weights)
