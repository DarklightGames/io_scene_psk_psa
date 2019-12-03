from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty
import ctypes
import struct
import io
from typing import Type
from .psk import Psk, Vector3, Quaternion
from .builder import PskBuilder

# https://me3explorer.fandom.com/wiki/PSK_File_Format
# https://docs.unrealengine.com/udk/Two/rsrc/Two/BinaryFormatSpecifications/UnrealAnimDataStructs.h
class PskExportOperator(Operator, ExportHelper):
    bl_idname = 'export.psk'
    bl_label = 'Export'
    __doc__ = 'PSK Exporter (.psk)'
    filename_ext = '.psk'
    # filter_glob : StringProperty(default='*.psk', options={'HIDDEN'})

    filepath : StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='')

    def execute(self, context):
        builder = PskBuilder()
        psk = builder.build(context)
        exporter = PskExporter(psk)
        exporter.export(self.filepath)
        return {'FINISHED'}


class PskExporter(object):
    def __init__(self, psk: Psk):
        self.psk: Psk = psk

    @staticmethod
    def write_section(fp, name: bytes, data_type: Type[ctypes.Structure] = None, data: list = None):
        section = Psk.Section()
        section.name = name
        if data_type is not None and data is not None:
            section.data_size = ctypes.sizeof(data_type)
            section.data_count = len(data)
        fp.write(section)
        if data is not None:
            for datum in data:
                fp.write(datum)

    def export(self, path: str):
        # TODO: add logic somewhere to assert lengths of ctype structs (pack1)
        with open(path, 'wb') as fp:
            self.write_section(fp, b'ACTRHEAD')

            # POINTS
            self.write_section(fp, b'PNTS0000', Vector3, self.psk.points)

            # WEDGES
            # TODO: would be nice to have this implicit!
            if len(self.psk.wedges) <= 65536:
                wedge_type = Psk.Wedge16
            else:
                wedge_type = Psk.Wedge32

            self.write_section(fp, b'VTXW0000', wedge_type, self.psk.wedges)

            # FACES
            self.write_section(fp, b'FACE0000', Psk.Face, self.psk.faces)

            # MATERIALS
            self.write_section(fp, b'MATT0000', Psk.Material, self.psk.materials)

            # BONES
            self.write_section(fp, b'REFSKELT', Psk.Bone, self.psk.bones)

            # WEIGHTS
            self.write_section(fp, b'RAWWEIGHTS', Psk.Weight, self.psk.weights)
