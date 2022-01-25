import bpy
from bpy.types import Operator, PropertyGroup, Action, UIList, BoneGroup, Panel
from bpy.props import CollectionProperty, IntProperty, PointerProperty, StringProperty, BoolProperty, EnumProperty
from bpy_extras.io_utils import ExportHelper
from typing import Type
from .builder import PsaBuilder, PsaBuilderOptions
from .data import *
from ..types import BoneGroupListItem
from ..helpers import *
from collections import Counter
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


def update_action_names(context):
    pg = context.scene.psa_export
    for item in pg.action_list:
        action = item.action
        item.action_name = get_psa_sequence_name(action, pg.should_use_original_sequence_names)


def should_use_original_sequence_names_updated(property, context):
    update_action_names(context)


class PsaExportPropertyGroup(PropertyGroup):
    action_list: CollectionProperty(type=PsaExportActionListItem)
    action_list_index: IntProperty(default=0)
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        description='',
        items=(
            ('ALL', 'All', 'All bones will be exported.'),
            ('BONE_GROUPS', 'Bone Groups', 'Only bones belonging to the selected bone groups and their ancestors will be exported.')
        )
    )
    bone_group_list: CollectionProperty(type=BoneGroupListItem)
    bone_group_list_index: IntProperty(default=0)
    should_use_original_sequence_names: BoolProperty(default=False, name='Original Names', description='If the action was imported from the PSA Import panel, the original name of the sequence will be used instead of the Blender action name', update=should_use_original_sequence_names_updated)


def is_bone_filter_mode_item_available(context, identifier):
    if identifier == 'BONE_GROUPS':
        obj = context.active_object
        if not obj.pose or not obj.pose.bone_groups:
            return False
    return True


class PsaExportOperator(Operator, ExportHelper):
    bl_idname = 'psa_export.operator'
    bl_label = 'Export'
    __doc__ = 'Export actions to PSA'
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
        pg = context.scene.psa_export

        # ACTIONS
        layout.label(text='Actions', icon='ACTION')
        row = layout.row(align=True)
        row.label(text='Select')
        row.operator(PsaExportSelectAll.bl_idname, text='All')
        row.operator(PsaExportDeselectAll.bl_idname, text='None')
        row = layout.row()
        rows = max(3, min(len(pg.action_list), 10))
        row.template_list('PSA_UL_ExportActionList', '', pg, 'action_list', pg, 'action_list_index', rows=rows)

        col = layout.column(heading="Options")
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(pg, 'should_use_original_sequence_names')

        # Determine if there is going to be a naming conflict and display an error, if so.
        selected_actions = [x for x in pg.action_list if x.is_selected]
        action_names = [x.action_name for x in selected_actions]
        action_name_counts = Counter(action_names)
        for action_name, count in action_name_counts.items():
            if count > 1:
                layout.label(text=f'Duplicate action: {action_name}', icon='ERROR')
                break

        layout.separator()

        # BONES
        box = layout.row()
        box.label(text='Bones', icon='BONE_DATA')
        bone_filter_mode_items = pg.bl_rna.properties['bone_filter_mode'].enum_items_static
        row = box.row(align=True)

        for item in bone_filter_mode_items:
            identifier = item.identifier
            item_layout = row.row(align=True)
            item_layout.prop_enum(pg, 'bone_filter_mode', item.identifier)
            item_layout.enabled = is_bone_filter_mode_item_available(context, identifier)

        if pg.bone_filter_mode == 'BONE_GROUPS':
            rows = max(3, min(len(pg.bone_group_list), 10))
            layout.template_list('PSX_UL_BoneGroupList', '', pg, 'bone_group_list', pg,
                              'bone_group_list_index', rows=rows)

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
        pg = context.scene.psa_export

        if context.view_layer.objects.active is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'An armature must be selected')
            return {'CANCELLED'}

        if context.view_layer.objects.active.type != 'ARMATURE':
            self.report({'ERROR_INVALID_CONTEXT'}, 'The selected object must be an armature.')
            return {'CANCELLED'}

        self.armature = context.view_layer.objects.active

        # Populate actions list.
        pg.action_list.clear()
        for action in bpy.data.actions:
            if not self.is_action_for_armature(action):
                continue
            item = pg.action_list.add()
            item.action = action
            item.action_name = action.name
            item.is_selected = True

        update_action_names(context)

        if len(pg.action_list) == 0:
            # If there are no actions at all, we have nothing to export, so just cancel the operation.
            self.report({'ERROR_INVALID_CONTEXT'}, 'There are no actions to export.')
            return {'CANCELLED'}

        # Populate bone groups list.
        populate_bone_group_list(self.armature, pg.bone_group_list)

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        pg = context.scene.psa_export
        actions = [x.action for x in pg.action_list if x.is_selected]

        if len(actions) == 0:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No actions were selected for export.')
            return {'CANCELLED'}

        options = PsaBuilderOptions()
        options.actions = actions
        options.bone_filter_mode = pg.bone_filter_mode
        options.bone_group_indices = [x.index for x in pg.bone_group_list if x.is_selected]
        options.should_use_original_sequence_names = pg.should_use_original_sequence_names
        builder = PsaBuilder()
        try:
            psa = builder.build(context, options)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}
        exporter = PsaExporter(psa)
        exporter.export(self.filepath)
        return {'FINISHED'}


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
    bl_description = 'Select all actions'

    @classmethod
    def poll(cls, context):
        pg = context.scene.psa_export
        action_list = pg.action_list
        has_unselected_actions = any(map(lambda action: not action.is_selected, action_list))
        return len(action_list) > 0 and has_unselected_actions

    def execute(self, context):
        pg = context.scene.psa_export
        for action in pg.action_list:
            action.is_selected = True
        return {'FINISHED'}


class PsaExportDeselectAll(bpy.types.Operator):
    bl_idname = 'psa_export.actions_deselect_all'
    bl_label = 'Deselect All'
    bl_description = 'Deselect all actions'

    @classmethod
    def poll(cls, context):
        pg = context.scene.psa_export
        action_list = pg.action_list
        has_selected_actions = any(map(lambda action: action.is_selected, action_list))
        return len(action_list) > 0 and has_selected_actions

    def execute(self, context):
        pg = context.scene.psa_export
        for action in pg.action_list:
            action.is_selected = False
        return {'FINISHED'}


classes = (
    PsaExportActionListItem,
    PsaExportPropertyGroup,
    PsaExportOperator,
    PSA_UL_ExportActionList,
    PsaExportSelectAll,
    PsaExportDeselectAll,
)
