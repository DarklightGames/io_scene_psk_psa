from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty
from .builder import PskBuilder
from .exporter import PskExporter
from .reader import PskReader
from .importer import PskImporter


class PskImportOperator(Operator, ImportHelper):
    bl_idname = 'import.psk'
    bl_label = 'Export'
    __doc__ = 'PSK Importer (.psk)'
    filename_ext = '.psk'
    filter_glob: StringProperty(default='*.psk', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='')

    def execute(self, context):
        reader = PskReader()
        psk = reader.read(self.filepath)
        PskImporter().import_psk(psk, context)
        return {'FINISHED'}


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
