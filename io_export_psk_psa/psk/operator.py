from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty
from .builder import PskBuilder
from .exporter import PskExporter


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
