from bpy.app.handlers import persistent

if 'bpy' in locals():
    import importlib

    importlib.reload(shared_data)
    importlib.reload(shared_helpers)
    importlib.reload(shared_types)
    importlib.reload(shared_dfs)
    importlib.reload(shared_ui)

    importlib.reload(psk_data)
    importlib.reload(psk_reader)
    importlib.reload(psk_writer)
    importlib.reload(psk_builder)
    importlib.reload(psk_importer)
    importlib.reload(psk_properties)
    importlib.reload(psk_ui)
    importlib.reload(psk_export_properties)
    importlib.reload(psk_export_operators)
    importlib.reload(psk_export_ui)
    importlib.reload(psk_import_operators)

    importlib.reload(psa_data)
    importlib.reload(psa_config)
    importlib.reload(psa_reader)
    importlib.reload(psa_writer)
    importlib.reload(psa_builder)
    importlib.reload(psa_importer)
    importlib.reload(psa_export_properties)
    importlib.reload(psa_export_operators)
    importlib.reload(psa_export_ui)
    importlib.reload(psa_import_properties)
    importlib.reload(psa_import_operators)
    importlib.reload(psa_import_ui)
else:
    from .shared import data as shared_data, types as shared_types, helpers as shared_helpers
    from .shared import dfs as shared_dfs, ui as shared_ui
    from .psk import (
        builder as psk_builder,
        data as psk_data,
        importer as psk_importer,
        properties as psk_properties,
        writer as psk_writer,
    )
    from .psk import reader as psk_reader, ui as psk_ui
    from .psk.export import (
        operators as psk_export_operators,
        properties as psk_export_properties,
        ui as psk_export_ui,
    )
    from .psk.import_ import operators as psk_import_operators

    from .psa import (
        config as psa_config,
        data as psa_data,
        writer as psa_writer,
        reader as psa_reader,
        builder as psa_builder,
        importer as psa_importer,
    )
    from .psa.export import (
        properties as psa_export_properties,
        ui as psa_export_ui,
        operators as psa_export_operators,
    )
    from .psa.import_ import operators as psa_import_operators
    from .psa.import_ import ui as psa_import_ui, properties as psa_import_properties

import bpy
from bpy.props import PointerProperty

classes = shared_types.classes + \
          psk_properties.classes + \
          psk_ui.classes + \
          psk_import_operators.classes + \
          psk_export_properties.classes + \
          psk_export_operators.classes + \
          psk_export_ui.classes + \
          psa_export_properties.classes + \
          psa_export_operators.classes + \
          psa_export_ui.classes + \
          psa_import_properties.classes + \
          psa_import_operators.classes + \
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
    bpy.types.Material.psk = PointerProperty(type=psk_properties.PSX_PG_material)
    bpy.types.Scene.psa_import = PointerProperty(type=psa_import_properties.PSA_PG_import)
    bpy.types.Scene.psa_export = PointerProperty(type=psa_export_properties.PSA_PG_export)
    bpy.types.Scene.psk_export = PointerProperty(type=psk_export_properties.PSK_PG_export)
    bpy.types.Action.psa_export = PointerProperty(type=shared_types.PSX_PG_action_export)


def unregister():
    del bpy.types.Material.psk
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


@persistent
def load_handler(dummy):
    # Convert old `psa_sequence_fps` property to new `psa_export.fps` property.
    # This is only needed for backwards compatibility with files that may have used older versions of the addon.
    for action in bpy.data.actions:
        if 'psa_sequence_fps' in action:
            action.psa_export.fps = action['psa_sequence_fps']
            del action['psa_sequence_fps']


bpy.app.handlers.load_post.append(load_handler)
