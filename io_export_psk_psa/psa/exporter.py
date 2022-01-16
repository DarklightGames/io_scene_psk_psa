import bpy
from bpy.types import Operator, PropertyGroup, Action
from bpy.props import CollectionProperty, IntProperty, PointerProperty, StringProperty, BoolProperty
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
    is_selected: BoolProperty(default=False)

    @property
    def name(self):
        return self.action.name


class PsaExportPropertyGroup(bpy.types.PropertyGroup):
    action_list: CollectionProperty(type=PsaExportActionListItem)
    import_action_list: CollectionProperty(type=PsaExportActionListItem)
    action_list_index: IntProperty(name='index for list??', default=0)
    import_action_list_index: IntProperty(name='index for list??', default=0)


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
        row.template_list('PSA_UL_ActionList', 'asd', scene.psa_export, 'action_list', scene.psa_export, 'action_list_index', rows=10)

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
        if context.view_layer.objects.active.type != 'ARMATURE':
            self.report({'ERROR_INVALID_CONTEXT'}, 'The selected object must be an armature.')
            return {'CANCELLED'}

        self.armature = context.view_layer.objects.active

        context.scene.psa_export.action_list.clear()
        for action in bpy.data.actions:
            item = context.scene.psa_export.action_list.add()
            item.action = action
            if self.is_action_for_armature(action):
                item.is_selected = True

        if len(context.scene.psa_export.action_list) == 0:
            self.report({'ERROR_INVALID_CONTEXT'}, 'There are no actions to export.')
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        actions = [x.action for x in context.scene.psa_export.action_list if x.is_selected]

        if len(actions) == 0:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No actions were selected for export.')
            return {'CANCELLED'}

        options = PsaBuilderOptions()
        options.actions = actions
        builder = PsaBuilder()
        psa = builder.build(context, options)
        exporter = PsaExporter(psa)
        exporter.export(self.filepath)
        return {'FINISHED'}
