from bpy.types import Context
from bpy.types import FileHandler

from .import_.operators import PSA_OT_import_drag_and_drop
from .export.operators import PSA_OT_export_collection

class PSA_FH_file_handler(FileHandler):
    bl_idname = 'PSA_FH_file_handler'
    bl_label = 'Unreal PSA'
    bl_import_operator = PSA_OT_import_drag_and_drop.bl_idname
    bl_export_operator = PSA_OT_export_collection.bl_idname
    bl_file_extensions = '.psa'

    @classmethod
    def poll_drop(cls, context: Context) -> bool:
        return context.area is not None and context.area.type == 'VIEW_3D'


_classes = (
    PSA_FH_file_handler,
)

from bpy.utils import register_classes_factory
register, unregister = register_classes_factory(_classes)
