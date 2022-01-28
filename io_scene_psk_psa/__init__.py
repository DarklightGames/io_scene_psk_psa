bl_info = {
    "name": "PSK/PSA Importer/Exporter",
    "author": "Colin Basnett",
    "version": (2, 1, 0),
    "blender": (2, 80, 0),
    # "location": "File > Export > PSK Export (.psk)",
    "description": "PSK/PSA Import/Export (.psk/.psa)",
    "warning": "",
    "doc_url": "https://github.com/DarklightGames/io_scene_psk_psa",
    "tracker_url": "https://github.com/DarklightGames/io_scene_psk_psa/issues",
    "category": "Import-Export"
}

if 'bpy' in locals():
    import importlib
    importlib.reload(psx_data)
    importlib.reload(psx_helpers)
    importlib.reload(psx_types)
    importlib.reload(psk_data)
    importlib.reload(psk_builder)
    importlib.reload(psk_exporter)
    importlib.reload(psk_importer)
    importlib.reload(psk_reader)
    importlib.reload(psa_data)
    importlib.reload(psa_builder)
    importlib.reload(psa_exporter)
    importlib.reload(psa_reader)
    importlib.reload(psa_importer)
else:
    # if i remove this line, it can be enabled just fine
    from . import data as psx_data
    from . import helpers as psx_helpers
    from . import types as psx_types
    from .psk import data as psk_data
    from .psk import builder as psk_builder
    from .psk import exporter as psk_exporter
    from .psk import reader as psk_reader
    from .psk import importer as psk_importer
    from .psa import data as psa_data
    from .psa import builder as psa_builder
    from .psa import exporter as psa_exporter
    from .psa import reader as psa_reader
    from .psa import importer as psa_importer


import bpy
from bpy.props import PointerProperty

classes = psx_types.__classes__ + \
          psk_importer.__classes__ + \
          psk_exporter.__classes__ + \
          psa_exporter.__classes__ + \
          psa_importer.__classes__


def psk_export_menu_func(self, context):
    self.layout.operator(psk_exporter.PskExportOperator.bl_idname, text='Unreal PSK (.psk)')


def psk_import_menu_func(self, context):
    self.layout.operator(psk_importer.PskImportOperator.bl_idname, text='Unreal PSK (.psk/.pskx)')


def psa_export_menu_func(self, context):
    self.layout.operator(psa_exporter.PsaExportOperator.bl_idname, text='Unreal PSA (.psa)')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(psk_export_menu_func)
    bpy.types.TOPBAR_MT_file_import.append(psk_import_menu_func)
    bpy.types.TOPBAR_MT_file_export.append(psa_export_menu_func)
    bpy.types.Scene.psa_import = PointerProperty(type=psa_importer.PsaImportPropertyGroup)
    bpy.types.Scene.psk_import = PointerProperty(type=psk_importer.PskImportPropertyGroup)
    bpy.types.Scene.psa_export = PointerProperty(type=psa_exporter.PsaExportPropertyGroup)
    bpy.types.Scene.psk_export = PointerProperty(type=psk_exporter.PskExportPropertyGroup)


def unregister():
    del bpy.types.Scene.psa_export
    del bpy.types.Scene.psa_import
    bpy.types.TOPBAR_MT_file_export.remove(psk_export_menu_func)
    bpy.types.TOPBAR_MT_file_import.remove(psk_import_menu_func)
    bpy.types.TOPBAR_MT_file_export.remove(psa_export_menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
