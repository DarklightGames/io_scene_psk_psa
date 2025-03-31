from bpy.types import UILayout

from .types import bone_filter_mode_items


def is_bone_filter_mode_item_available(pg, identifier):
    if identifier == 'BONE_COLLECTIONS' and len(pg.bone_collection_list) == 0:
        return False
    return True


def draw_bone_filter_mode(layout: UILayout, pg, should_always_show_bone_collections=False):
    row = layout.row(align=True)
    for item_identifier, _, _ in bone_filter_mode_items:
        identifier = item_identifier
        item_layout = row.row(align=True)
        item_layout.prop_enum(pg, 'bone_filter_mode', item_identifier)
        item_layout.enabled = should_always_show_bone_collections or is_bone_filter_mode_item_available(pg, identifier)
