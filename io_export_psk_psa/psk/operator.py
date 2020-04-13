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
        object = context.view_layer.objects.active

        if object.type != 'MESH':
            self.report({'ERROR_INVALID_CONTEXT'}, 'The selected object must be a mesh.')
            return {'CANCELLED'}

        if len(object.data.materials) == 0:
            self.report({'ERROR_INVALID_CONTEXT'}, 'Mesh must have at least one material')
            return {'CANCELLED'}

        # ensure that there is exactly one armature modifier
        modifiers = [x for x in object.modifiers if x.type == 'ARMATURE']

        if len(modifiers) != 1:
            self.report({'ERROR_INVALID_CONTEXT'}, 'Mesh must have one armature modifier')
            return {'CANCELLED'}

        armature_modifier = modifiers[0]
        armature_object = armature_modifier.object

        if object.modifiers[-1] != armature_modifier:
            self.report({'ERROR_INVALID_CONTEXT'}, 'Armature modifier must be the last modifier in the stack')
            return {'CANCELLED'}

        if armature_object is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'Armature modifier has no linked object')
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        builder = PskBuilder()
        psk = builder.build(context)
        exporter = PskExporter(psk)
        exporter.export(self.filepath)
        return {'FINISHED'}
