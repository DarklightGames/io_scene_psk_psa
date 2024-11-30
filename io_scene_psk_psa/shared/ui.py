from bpy.types import UILayout

from .data import bone_filter_mode_items


def is_bone_filter_mode_item_available(pg, identifier):
    match identifier:
        case 'BONE_COLLECTIONS':
            if len(pg.bone_collection_list) == 0:
                return False
        case _:
            pass
    return True


def draw_bone_filter_mode(layout: UILayout, pg):
    row = layout.row(align=True)
    for item_identifier, _, _ in bone_filter_mode_items:
        identifier = item_identifier
        item_layout = row.row(align=True)
        item_layout.prop_enum(pg, 'bone_filter_mode', item_identifier)
        item_layout.enabled = is_bone_filter_mode_item_available(pg, identifier)
