bl_info = {
    "name": "PSK/PSA Importer/Exporter",
    "author": "Colin Basnett, Yurii Ti",
    "version": (5, 0, 4),
    "blender": (3, 4, 0),
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
    importlib.reload(psk_reader)
    importlib.reload(psk_writer)
    importlib.reload(psk_builder)
    importlib.reload(psk_importer)
    importlib.reload(psk_export_properties)
    importlib.reload(psk_export_operators)
    importlib.reload(psk_export_ui)
    importlib.reload(psk_import_operators)

    importlib.reload(psa_data)
    importlib.reload(psa_reader)
    importlib.reload(psa_writer)
    importlib.reload(psa_builder)
    importlib.reload(psa_export_properties)
    importlib.reload(psa_export_operators)
    importlib.reload(psa_export_ui)
    importlib.reload(psa_import_properties)
    importlib.reload(psa_import_operators)
    importlib.reload(psa_import_ui)
else:
    # if i remove this line, it can be enabled just fine
    from . import data as psx_data
    from . import helpers as psx_helpers
    from . import types as psx_types
    from .psk import data as psk_data
    from .psk import reader as psk_reader
    from .psk import writer as psk_writer
    from .psk import builder as psk_builder
    from .psk import importer as psk_importer
    from .psk.export import properties as psk_export_properties
    from .psk.export import operators as psk_export_operators
    from .psk.export import ui as psk_export_ui
    from .psk.import_ import operators as psk_import_operators

    from .psa import data as psa_data
    from .psa import reader as psa_reader
    from .psa import writer as psa_writer
    from .psa import builder as psa_builder
    from .psa import importer as psa_importer
    from .psa.export import properties as psa_export_properties
    from .psa.export import operators as psa_export_operators
    from .psa.export import ui as psa_export_ui
    from .psa.import_ import properties as psa_import_properties
    from .psa.import_ import operators as psa_import_operators
    from .psa.import_ import ui as psa_import_ui

import bpy
from bpy.props import PointerProperty

classes = psx_types.classes +\
          psk_import_operators.classes +\
          psk_export_properties.classes +\
          psk_export_operators.classes +\
          psk_export_ui.classes + \
          psa_export_properties.classes +\
          psa_export_operators.classes +\
          psa_export_ui.classes + \
          psa_import_properties.classes +\
          psa_import_operators.classes +\
          psa_import_ui.classes


def psk_export_menu_func(self, context):
    self.layout.operator(psk_export_operators.PSK_OT_export.bl_idname, text='Unreal PSK (.psk)')


def psk_import_menu_func(self, context):
    self.layout.operator(psk_import_operators.PSK_OT_import.bl_idname, text='Unreal PSK (.psk/.pskx)')


def psa_export_menu_func(self, context):
    self.layout.operator(psa_export_operators.PSA_OT_export.bl_idname, text='Unreal PSA (.psa)')


def psa_import_menu_func(self, context):
    self.layout.operator(psa_import_operators.PSA_OT_import.bl_idname, text='Unreal PSA (.psa)')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(psk_export_menu_func)
    bpy.types.TOPBAR_MT_file_import.append(psk_import_menu_func)
    bpy.types.TOPBAR_MT_file_export.append(psa_export_menu_func)
    bpy.types.TOPBAR_MT_file_import.append(psa_import_menu_func)
    bpy.types.Scene.psa_import = PointerProperty(type=psa_import_properties.PSA_PG_import)
    bpy.types.Scene.psa_export = PointerProperty(type=psa_export_properties.PSA_PG_export)
    bpy.types.Scene.psk_export = PointerProperty(type=psk_export_properties.PSK_PG_export)
    bpy.types.Action.psa_export = PointerProperty(type=psx_types.PSX_PG_action_export)


def unregister():
    del bpy.types.Scene.psa_import
    del bpy.types.Scene.psa_export
    del bpy.types.Scene.psk_export
    del bpy.types.Action.psa_export
    bpy.types.TOPBAR_MT_file_export.remove(psk_export_menu_func)
    bpy.types.TOPBAR_MT_file_import.remove(psk_import_menu_func)
    bpy.types.TOPBAR_MT_file_export.remove(psa_export_menu_func)
    bpy.types.TOPBAR_MT_file_import.remove(psa_import_menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
