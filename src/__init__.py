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
    importlib.reload(psk_data)
    importlib.reload(psk_builder)
    importlib.reload(psk_exporter)
    importlib.reload(psk_operator)
    importlib.reload(psa_data)
    importlib.reload(psa_builder)
    importlib.reload(psa_exporter)
    importlib.reload(psa_operator)
else:
    # if i remove this line, it can be enabled just fine
    from .psk import data as psk_data
    from .psk import builder as psk_builder
    from .psk import exporter as psk_exporter
    from .psk import operator as psk_operator
    from .psa import data as psa_data
    from .psa import builder as psa_builder
    from .psa import exporter as psa_exporter
    from .psa import operator as psa_operator

import bpy

classes = [
    psk_operator.PskExportOperator,
    psa_operator.PsaExportOperator
]

def psk_menu_func(self, context):
    self.layout.operator(psk_operator.PskExportOperator.bl_idname, text ='Unreal PSK (.psk)')

def psa_menu_func(self, context):
    self.layout.operator(psa_operator.PsaExportOperator.bl_idname, text='Unreal PSA (.psa)')

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(psk_menu_func)
    bpy.types.TOPBAR_MT_file_export.append(psa_menu_func)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(psa_menu_func)
    bpy.types.TOPBAR_MT_file_export.remove(psk_menu_func)
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)

if __name__ == '__main__':
    register()
