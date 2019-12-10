from bpy.types import Operator, Action
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty, CollectionProperty
from .builder import PsaBuilder
from .exporter import PsaExporter


class PsaExportOperator(Operator, ExportHelper):
    bl_idname = 'export.psa'
    bl_label = 'Export'
    __doc__ = 'PSA Exporter (.psa)'
    filename_ext = '.psa'
    filter_glob : StringProperty(default='*.psa', options={'HIDDEN'})

    filepath : StringProperty(
        name='File Path',
        description='File path used for exporting the PSA file',
        maxlen=1024,
        default='')

    actions : CollectionProperty(
        type=Action,
        name='Sequences'
    )

    def execute(self, context):
        builder = PsaBuilder()
        psk = builder.build(context)
        exporter = PsaExporter(psk)
        exporter.export(self.filepath)
        return {'FINISHED'}
