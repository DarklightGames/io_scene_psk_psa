from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty
import struct
import io
from .psk import Psk
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
    def write_section(f, id: bytes, data_size: int, data_count: int, data: bytes):
        write(f, '20s', bytearray(id).ljust(20, b'\0'))
        write(f, 'I', 1999801)
        write(f, 'I', data_size)
        write(f, 'I', data_count)
        f.write(data)


    def export(self, path: str):
        with open(path, 'wb') as fp:
            PskExporter.write_section(fp, b'ACTRHEAD', 0, 0, b'')

            # POINTS
            data = io.BytesIO()
            fmt = '3f'
            for point in self.psk.points:
                write(data, fmt, point.x, point.y, point.z)
            PskExporter.write_section(fp, b'PNTS0000', struct.calcsize(fmt), len(self.psk.points), data.getvalue())

            # WEDGES
            buffer = io.BytesIO()
            if len(self.psk.wedges) <= 65536:
                for w in self.psk.wedges:
                    write(buffer, 'ssffbbs', w.point_index, 0, w.u, w.v, w.material_index, 0, 0)
            else:
                for w in self.psk.wedges:
                    write(buffer, 'iffi', w.point_index, w.u, w.v, w.material_index)
            fp.write(buffer.getvalue())

            # FACES
            buffer = io.BytesIO()
            for f in self.psk.faces:
                write(buffer, 'sssbbi', f.wedge_index_1, f.wedge_index_2, f.wedge_index_3, f.material_index,
                      f.aux_material_index, f.smoothing_groups)
            fp.write(buffer.getvalue())

            # MATERIALS
            buffer = io.BytesIO()
            fmt = '64s6i'
            for m in self.psk.materials:
                write(buffer, fmt, bytes(m.name, encoding='utf-8'), m.texture_index, m.poly_flags, m.aux_material_index, m.aux_flags, m.lod_bias, m.lod_style)
            self.write_section(fp, b'MATT0000', struct.calcsize(fmt), len(self.psk.materials), buffer.getvalue())


def write(f, fmt, *values):
    f.write(struct.pack(fmt, *values))
