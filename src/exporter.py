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
        # TODO: we should use ctypes, would be cleaner and faster
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
            data = io.BytesIO()
            if len(self.psk.wedges) <= 65536:
                fmt = 'hhffbbh'
                for w in self.psk.wedges:
                    # NOTE: there's some sort of problem here where the wedges mtl indx is wrong
                    # in the documentation.
                    write(data, fmt, w.point_index, 0, w.u, w.v, w.material_index, w.material_index, 0)
            else:
                fmt = 'iffi'
                for w in self.psk.wedges:
                    write(data, fmt, w.point_index, w.u, w.v, w.material_index)
            PskExporter.write_section(fp, b'VTXW0000', struct.calcsize(fmt), len(self.psk.wedges), data.getvalue())

            # FACES
            data = io.BytesIO()
            fmt = 'HHHbbi'
            for f in self.psk.faces:
                write(data, fmt, f.wedge_index_1, f.wedge_index_2, f.wedge_index_3, f.material_index,
                      f.aux_material_index, f.smoothing_groups)
            PskExporter.write_section(fp, b'FACE0000', struct.calcsize(fmt), len(self.psk.faces), data.getvalue())

            # MATERIALS
            data = io.BytesIO()
            fmt = '64s6i'
            for m in self.psk.materials:
                write(data, fmt, bytes(m.name, encoding='utf-8'), m.texture_index, m.poly_flags, m.aux_material_index, m.aux_flags, m.lod_bias, m.lod_style)
            self.write_section(fp, b'MATT0000', struct.calcsize(fmt), len(self.psk.materials), data.getvalue())

            # BONES
            data = io.BytesIO()
            fmt = '64s3i11f'
            for b in self.psk.bones:
                write(data, fmt, bytes(b.name, encoding='utf-8'),
                      b.flags, b.children_count, b.parent_index, b.rotation.x, b.rotation.y, b.rotation.z,
                      b.rotation.w, b.position.x, b.position.y, b.position.z, b.length, b.size.x, b.size.y, b.size.z)
            self.write_section(fp, b'REFSKELT', struct.calcsize(fmt), len(self.psk.bones), data.getvalue())

            # WEIGHTS
            data = io.BytesIO()
            fmt = 'f2i'
            for w in self.psk.weights:
                print(w.weight, w.point_index, w.bone_index)
                write(data, fmt, w.weight, w.point_index, w.bone_index)
            self.write_section(fp, b'RAWWEIGHTS', struct.calcsize(fmt), len(self.psk.weights), data.getvalue())


def write(f, fmt, *values):
    f.write(struct.pack(fmt, *values))
