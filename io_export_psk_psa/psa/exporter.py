import bpy
from bpy.types import Operator, PropertyGroup, Action, UIList, BoneGroup
from bpy.props import CollectionProperty, IntProperty, PointerProperty, StringProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ExportHelper
from typing import Type
from .builder import PsaBuilder, PsaBuilderOptions
from .data import *
import re


class PsaExporter(object):
    def __init__(self, psa: Psa):
        self.psa: Psa = psa

    # This method is shared by both PSA/K file formats, move this?
    @staticmethod
    def write_section(fp, name: bytes, data_type: Type[Structure] = None, data: list = None):
        section = Section()
        section.name = name
        if data_type is not None and data is not None:
            section.data_size = sizeof(data_type)
            section.data_count = len(data)
        fp.write(section)
        if data is not None:
            for datum in data:
                fp.write(datum)

    def export(self, path: str):
        with open(path, 'wb') as fp:
            self.write_section(fp, b'ANIMHEAD')
            self.write_section(fp, b'BONENAMES', Psa.Bone, self.psa.bones)
            self.write_section(fp, b'ANIMINFO', Psa.Sequence, list(self.psa.sequences.values()))
            self.write_section(fp, b'ANIMKEYS', Psa.Key, self.psa.keys)


class PsaExportActionListItem(PropertyGroup):
    action: PointerProperty(type=Action)
    action_name: StringProperty()
    is_selected: BoolProperty(default=False)

    @property
    def name(self):
        return self.action.name


class PsaExportBoneGroupListItem(PropertyGroup):
    name: StringProperty()
    index: IntProperty()
    is_selected: BoolProperty(default=False)

    @property
    def name(self):
        return self.bone_group.name


class PsaExportPropertyGroup(PropertyGroup):
    action_list: CollectionProperty(type=PsaExportActionListItem)
    action_list_index: IntProperty(default=0)
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        items={
            ('NONE', 'None', 'All bones will be exported.'),
            ('BONE_GROUPS', 'Bone Groups', 'Only bones belonging to the selected bone groups will be exported.'),
        }
    )
    bone_group_list: CollectionProperty(type=PsaExportBoneGroupListItem)
    bone_group_list_index: IntProperty(default=0)


class PsaExportOperator(Operator, ExportHelper):
    bl_idname = 'export.psa'
    bl_label = 'Export'
    __doc__ = 'PSA Exporter (.psa)'
    filename_ext = '.psa'
    filter_glob: StringProperty(default='*.psa', options={'HIDDEN'})
    filepath: StringProperty(
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
        row.template_list('PSA_UL_ExportActionList', 'asd', scene.psa_export, 'action_list', scene.psa_export, 'action_list_index', rows=10)

        row = box.row()
        row.operator('psa_export.actions_select_all', text='Select All')
        row.operator('psa_export.actions_deselect_all', text='Deselect All')

        box = layout.box()
        box.label(text='Bone Filter', icon='FILTER')

        row = box.row()
        row.alignment = 'EXPAND'
        row.prop(scene.psa_export, 'bone_filter_mode', expand=True, text='Bone Filter')

        if scene.psa_export.bone_filter_mode == 'BONE_GROUPS':
            row = box.row()
            rows = max(3, min(len(scene.psa_export.bone_group_list), 10))
            row.template_list('PSA_UL_ExportBoneGroupList', 'asd', scene.psa_export, 'bone_group_list', scene.psa_export, 'bone_group_list_index', rows=rows)

    def is_action_for_armature(self, action):
        if len(action.fcurves) == 0:
            return False
        bone_names = set([x.name for x in self.armature.data.bones])
        for fcurve in action.fcurves:
            match = re.match(r'pose\.bones\["(.+)"\].\w+', fcurve.data_path)
            if not match:
                continue
            bone_name = match.group(1)
            if bone_name in bone_names:
                return True
        return False

    def invoke(self, context, event):
        if context.view_layer.objects.active is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'An armature must be selected')
            return {'CANCELLED'}

        if context.view_layer.objects.active.type != 'ARMATURE':
            self.report({'ERROR_INVALID_CONTEXT'}, 'The selected object must be an armature.')
            return {'CANCELLED'}

        self.armature = context.view_layer.objects.active

        # Populate actions list.
        context.scene.psa_export.action_list.clear()
        for action in bpy.data.actions:
            item = context.scene.psa_export.action_list.add()
            item.action = action
            item.action_name = action.name
            if self.is_action_for_armature(action):
                item.is_selected = True

        if len(context.scene.psa_export.action_list) == 0:
            # If there are no actions at all, we have nothing to export, so just cancel the operation.
            self.report({'ERROR_INVALID_CONTEXT'}, 'There are no actions to export.')
            return {'CANCELLED'}

        # Populate bone groups list.
        context.scene.psa_export.bone_group_list.clear()
        for bone_group_index, bone_group in enumerate(self.armature.pose.bone_groups):
            item = context.scene.psa_export.bone_group_list.add()
            item.name = bone_group.name
            item.index = bone_group_index
            item.is_selected = False

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        actions = [x.action for x in context.scene.psa_export.action_list if x.is_selected]

        if len(actions) == 0:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No actions were selected for export.')
            return {'CANCELLED'}

        options = PsaBuilderOptions()
        options.actions = actions
        options.bone_filter_mode = context.scene.psa_export.bone_filter_mode
        options.bone_group_indices = [x.index for x in context.scene.psa_export.bone_group_list if x.is_selected]
        builder = PsaBuilder()
        psa = builder.build(context, options)
        exporter = PsaExporter(psa)
        exporter.export(self.filepath)
        return {'FINISHED'}


class PSA_UL_ExportBoneGroupList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.alignment = 'LEFT'
        layout.prop(item, 'is_selected', icon_only=True)
        layout.label(text=item.name, icon='GROUP_BONE')


class PSA_UL_ExportActionList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.alignment = 'LEFT'
        layout.prop(item, 'is_selected', icon_only=True)
        layout.label(text=item.action_name)

    def filter_items(self, context, data, property):
        actions = getattr(data, property)
        flt_flags = []
        flt_neworder = []
        if self.filter_name:
            flt_flags = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name,
                self.bitflag_filter_item,
                actions,
                'action_name',
                reverse=self.use_filter_invert
            )
        return flt_flags, flt_neworder


class PsaExportSelectAll(bpy.types.Operator):
    bl_idname = 'psa_export.actions_select_all'
    bl_label = 'Select All'

    @classmethod
    def poll(cls, context):
        action_list = context.scene.psa_export.action_list
        has_unselected_actions = any(map(lambda action: not action.is_selected, action_list))
        return len(action_list) > 0 and has_unselected_actions

    def execute(self, context):
        for action in context.scene.psa_export.action_list:
            action.is_selected = True
        return {'FINISHED'}


class PsaExportDeselectAll(bpy.types.Operator):
    bl_idname = 'psa_export.actions_deselect_all'
    bl_label = 'Deselect All'

    @classmethod
    def poll(cls, context):
        action_list = context.scene.psa_export.action_list
        has_selected_actions = any(map(lambda action: action.is_selected, action_list))
        return len(action_list) > 0 and has_selected_actions

    def execute(self, context):
        for action in context.scene.psa_export.action_list:
            action.is_selected = False
        return {'FINISHED'}
