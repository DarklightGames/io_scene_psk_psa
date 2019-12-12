from bpy.types import Operator, Action, UIList, PropertyGroup
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, FloatProperty, CollectionProperty, PointerProperty
from .builder import PsaBuilder
from .exporter import PsaExporter
import bpy
import re


class ActionListItem(PropertyGroup):
    action: PointerProperty(type=Action)
    is_selected: BoolProperty(default=False)

    @property
    def name(self):
        return self.action.name


class PSA_UL_ActionList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.alignment = 'LEFT'
        layout.prop(item, 'is_selected', icon_only=True)
        layout.label(text=item.action.name, icon='ACTION')

    def filter_items(self, context, data, property):
        # TODO: returns two lists, apparently
        actions = getattr(data, property)
        flt_flags = []
        flt_neworder = []
        if self.filter_name:
            flt_flags = bpy.types.UI_UL_list.filter_items_by_name(self.filter_name, self.bitflag_filter_item, actions, 'name', reverse=self.use_filter_invert)
        return flt_flags, flt_neworder


class PsaExportOperator(Operator, ExportHelper):
    bl_idname = 'export.psa'
    bl_label = 'Export'
    __doc__ = 'PSA Exporter (.psa)'
    filename_ext = '.psa'
    filter_glob : StringProperty(default='*.psa', options={'HIDDEN'})
    filepath : StringProperty(
        name='File Path',
        description='File path used for exporting the PSA file',
        maxlen=1024,
        default='')

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()
        row.label(text='Actions')
        row = layout.row()
        row.template_list('PSA_UL_ActionList', 'asd', scene, 'psa_action_list', scene, 'psa_action_list_index', rows=len(context.scene.psa_action_list))

    def invoke(self, context, event):
        if context.view_layer.objects.active.type != 'ARMATURE':
            self.report({'ERROR_INVALID_CONTEXT'}, 'The selected object must be an armature.')
            return {'CANCELLED'}
        context.scene.psa_action_list.clear()
        for action in bpy.data.actions:
            item = context.scene.psa_action_list.add()
            item.action = action
            # TODO: add
            item.is_selected = True
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        builder = PsaBuilder()
        psk = builder.build(context)
        exporter = PsaExporter(psk)
        exporter.export(self.filepath)
        return {'FINISHED'}
