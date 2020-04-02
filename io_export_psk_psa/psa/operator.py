from bpy.types import Operator, Action, UIList, PropertyGroup
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, CollectionProperty, PointerProperty
from .builder import PsaBuilder, PsaBuilderOptions
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
        layout.label(text=item.action.name)

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

    def __init__(self):
        self.armature = None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        box = layout.box()
        box.label(text='Actions', icon='ACTION')
        row = box.row()
        row.template_list('PSA_UL_ActionList', 'asd', scene, 'psa_action_list', scene, 'psa_action_list_index', rows=len(context.scene.psa_action_list))

    def is_action_for_armature(self, action):
        bone_names = [x.name for x in self.armature.data.bones]
        print(bone_names)
        for fcurve in action.fcurves:
            match = re.match('pose\.bones\["(.+)"\].\w+', fcurve.data_path)
            if not match:
                continue
            bone_name = match.group(1)
            if bone_name not in bone_names:
                return False
        return True

    def invoke(self, context, event):
        if context.view_layer.objects.active.type != 'ARMATURE':
            self.report({'ERROR_INVALID_CONTEXT'}, 'The selected object must be an armature.')
            return {'CANCELLED'}

        self.armature = context.view_layer.objects.active

        context.scene.psa_action_list.clear()
        for action in bpy.data.actions:
            item = context.scene.psa_action_list.add()
            item.action = action
            if self.is_action_for_armature(action):
                item.is_selected = True

        if len(context.scene.psa_action_list) == 0:
            self.report({'ERROR_INVALID_CONTEXT'}, 'There are no actions to export.')
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        actions = [x.action for x in context.scene.psa_action_list if x.is_selected]

        if len(actions) == 0:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No actions were selected for export.')
            return {'CANCELLED'}

        options = PsaBuilderOptions()
        options.actions = actions
        builder = PsaBuilder()
        psk = builder.build(context, options)
        exporter = PsaExporter(psk)
        exporter.export(self.filepath)
        return {'FINISHED'}
