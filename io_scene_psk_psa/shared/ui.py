import bpy
from bpy.types import Context, UILayout, Panel

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


class PSX_PT_scene(Panel):
    bl_idname = 'PSX_PT_scene'
    bl_label = 'PSK Export'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_category = 'PSK/PSA'

    @classmethod
    def poll(cls, context):
        return context.scene is not None
    
    def draw(self, context: Context):
        layout = self.layout
        scene = bpy.context.scene
        psx_export = getattr(scene, 'psx_export', None)
        if psx_export is None:
            return
        
        # Transform
        transform_header, transform_panel = layout.panel('Transform', default_closed=False)
        transform_header.label(text='Transform')
        if transform_panel:
            flow = layout.grid_flow(columns=1)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(psx_export, 'scale')
            flow.prop(psx_export, 'forward_axis')
            flow.prop(psx_export, 'up_axis')


classes = (
    PSX_PT_scene,
)
