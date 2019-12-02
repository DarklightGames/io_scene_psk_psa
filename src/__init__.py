bl_info = {
    "name": "PSK/PSA Exporter",
    "author": "Colin Basnett",
    "version": ( 1, 0, 0 ),
    "blender": ( 2, 80, 0 ),
    "location": "File > Export > PSK Export (.psk)",
    "description": "PSK/PSA Export (.psk)",
    "warning": "",
    "wiki_url": "https://github.com/DarklightGames/io_export_psk_psa",
    "tracker_url": "https://github.com/DarklightGames/io_export_psk_psa/issues",
    "category": "Import-Export"
}

if 'bpy' in locals():
    import importlib
    importlib.reload(psk)
    importlib.reload(exporter)
    importlib.reload(builder)
else:
    # if i remove this line, it can be enabled just fine
    from . import psk
    from . import exporter
    from . import builder

import bpy

classes = [
    exporter.PskExportOperator
]

def menu_func(self, context):
    self.layout.operator(exporter.PskExportOperator.bl_idname, text = "Unreal PSK (.psk)")

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

if __name__ == '__main__':
    register()
