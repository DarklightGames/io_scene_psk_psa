from .data import *
from .builder import PskBuilder
from typing import Type
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty

MAX_WEDGE_COUNT = 65536
MAX_POINT_COUNT = 4294967296
MAX_BONE_COUNT = 256
MAX_MATERIAL_COUNT = 256


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
        if len(self.psk.wedges) > MAX_WEDGE_COUNT:
            raise RuntimeError(f'Number of wedges ({len(self.psk.wedges)}) exceeds limit of {MAX_WEDGE_COUNT}')
        if len(self.psk.bones) > MAX_BONE_COUNT:
            raise RuntimeError(f'Number of bones ({len(self.psk.bones)}) exceeds limit of {MAX_BONE_COUNT}')
        if len(self.psk.points) > MAX_POINT_COUNT:
            raise RuntimeError(f'Numbers of vertices ({len(self.psk.points)}) exceeds limit of {MAX_POINT_COUNT}')
        if len(self.psk.materials) > MAX_MATERIAL_COUNT:
            raise RuntimeError(f'Number of materials ({len(self.psk.materials)}) exceeds limit of {MAX_MATERIAL_COUNT}')

        with open(path, 'wb') as fp:
            self.write_section(fp, b'ACTRHEAD')
            self.write_section(fp, b'PNTS0000', Vector3, self.psk.points)

            wedges = []
            for index, w in enumerate(self.psk.wedges):
                wedge = Psk.Wedge16()
                wedge.material_index = w.material_index
                wedge.u = w.u
                wedge.v = w.v
                wedge.point_index = w.point_index
                wedges.append(wedge)

            self.write_section(fp, b'VTXW0000', Psk.Wedge16, wedges)
            self.write_section(fp, b'FACE0000', Psk.Face, self.psk.faces)
            self.write_section(fp, b'MATT0000', Psk.Material, self.psk.materials)
            self.write_section(fp, b'REFSKELT', Psk.Bone, self.psk.bones)
            self.write_section(fp, b'RAWWEIGHTS', Psk.Weight, self.psk.weights)


class PskExportOperator(Operator, ExportHelper):
    bl_idname = 'export.psk'
    bl_label = 'Export'
    __doc__ = 'PSK Exporter (.psk)'
    filename_ext = '.psk'
    filter_glob: StringProperty(default='*.psk', options={'HIDDEN'})

    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='')

    def invoke(self, context, event):
        try:
            PskBuilder.get_input_objects(context)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        builder = PskBuilder()
        psk = builder.build(context)
        exporter = PskExporter(psk)
        exporter.export(self.filepath)
        return {'FINISHED'}
