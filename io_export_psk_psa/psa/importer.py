import bpy
import mathutils
from .data import Psa
from typing import List, AnyStr
import bpy
from bpy.types import Operator, Action, UIList, PropertyGroup, Panel, Armature
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy.props import StringProperty, BoolProperty, CollectionProperty, PointerProperty, IntProperty
from .reader import PsaReader


class PsaImporter(object):
    def __init__(self):
        pass

    def import_psa(self, psa: Psa, sequence_names: List[AnyStr], context):
        properties = context.scene.psa_import
        sequences = map(lambda x: psa.sequences[x], sequence_names)

        armature_object = properties.armature_object
        armature_data = armature_object.data

        # create an index mapping from bones in the PSA to bones in the target armature.
        bone_indices = {}
        data_bone_names = [x.name for x in armature_data.bones]
        for index, psa_bone in enumerate(psa.bones):
            psa_bone_name = psa_bone.name.decode()
            try:
                bone_indices[index] = data_bone_names.index(psa_bone_name)
            except ValueError:
                pass
        del data_bone_names

        for sequence in sequences:
            action = bpy.data.actions.new(name=sequence.name.decode())
            for psa_bone_index, armature_bone_index in bone_indices.items():
                psa_bone = psa.bones[psa_bone_index]
                pose_bone = armature_object.pose.bones[armature_bone_index]

                # rotation
                rotation_data_path = pose_bone.path_from_id('rotation_quaternion')
                fcurve_quat_w = action.fcurves.new(rotation_data_path, index=0)
                fcurve_quat_x = action.fcurves.new(rotation_data_path, index=0)
                fcurve_quat_y = action.fcurves.new(rotation_data_path, index=0)
                fcurve_quat_z = action.fcurves.new(rotation_data_path, index=0)

                # location
                location_data_path = pose_bone.path_from_id('location')
                fcurve_location_x = action.fcurves.new(location_data_path, index=0)
                fcurve_location_y = action.fcurves.new(location_data_path, index=1)
                fcurve_location_z = action.fcurves.new(location_data_path, index=2)

                # add keyframes
                fcurve_quat_w.keyframe_points.add(sequence.frame_count)
                fcurve_quat_x.keyframe_points.add(sequence.frame_count)
                fcurve_quat_y.keyframe_points.add(sequence.frame_count)
                fcurve_quat_z.keyframe_points.add(sequence.frame_count)
                fcurve_location_x.keyframe_points.add(sequence.frame_count)
                fcurve_location_y.keyframe_points.add(sequence.frame_count)
                fcurve_location_z.keyframe_points.add(sequence.frame_count)

            raw_key_index = 0   # ?
            for frame_index in range(sequence.frame_count):
                for psa_bone_index in range(len(psa.bones)):
                    if psa_bone_index not in bone_indices:
                        # bone does not exist in the armature, skip it
                        raw_key_index += 1
                        continue
                    psa_bone = psa.bones[psa_bone_index]

                    # ...

                    raw_key_index += 1


class PsaImportActionListItem(PropertyGroup):
    action_name: StringProperty()
    is_selected: BoolProperty(default=True)

    @property
    def name(self):
        return self.action_name


class PsaImportPropertyGroup(bpy.types.PropertyGroup):
    cool_filepath: StringProperty(default='')
    armature_object: PointerProperty(type=bpy.types.Object)  # TODO: figure out how to filter this to only objects of a specific type
    action_list: CollectionProperty(type=PsaImportActionListItem)
    import_action_list: CollectionProperty(type=PsaImportActionListItem)
    action_list_index: IntProperty(name='index for list??', default=0)
    import_action_list_index: IntProperty(name='index for list??', default=0)


class PSA_UL_ImportActionList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.alignment = 'LEFT'
        layout.prop(item, 'is_selected', icon_only=True)
        layout.label(text=item.action_name)

    def filter_items(self, context, data, property):
        # TODO: returns two lists, apparently
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


class PsaImportSelectAll(bpy.types.Operator):
    bl_idname = 'psa_import.actions_select_all'
    bl_label = 'Select All'

    def execute(self, context):
        for action in context.scene.psa_import.action_list:
            action.is_selected = True
        return {'FINISHED'}


class PsaImportDeselectAll(bpy.types.Operator):
    bl_idname = 'psa_import.actions_deselect_all'
    bl_label = 'Deselect All'

    def execute(self, context):
        for action in context.scene.psa_import.action_list:
            action.is_selected = False
        return {'FINISHED'}


class PSA_PT_ImportPanel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_label = 'PSA Import'
    bl_context = 'objectmode'
    bl_category = 'PSA Import'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        row = layout.row()
        row.operator('psa_import.file_select', icon='FILE_FOLDER', text='')
        row.label(text=scene.psa_import.cool_filepath)
        box = layout.box()
        box.label(text='Actions', icon='ACTION')
        row = box.row()
        row.template_list('PSA_UL_ImportActionList', 'asd', scene.psa_import, 'action_list', scene.psa_import, 'action_list_index', rows=10)
        row = box.row()
        row.operator('psa_import.actions_select_all', text='Select All')
        row.operator('psa_import.actions_deselect_all', text='Deselect All')
        layout.prop(scene.psa_import, 'armature_object', icon_only=True)
        layout.operator('psa_import.import', text='Import')


class PsaImportOperator(Operator):
    bl_idname = 'psa_import.import'
    bl_label = 'Import'

    def execute(self, context):
        psa = PsaReader().read(context.scene.psa_import.cool_filepath)
        sequence_names = [x.action_name for x in context.scene.psa_import.action_list if x.is_selected]
        PsaImporter().import_psa(psa, sequence_names, context)
        return {'FINISHED'}


class PsaImportFileSelectOperator(Operator, ImportHelper):
    bl_idname = 'psa_import.file_select'
    bl_label = 'File Select'
    filename_ext = '.psa'
    filter_glob: StringProperty(default='*.psa', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for importing the PSA file',
        maxlen=1024,
        default='')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        context.scene.psa_import.cool_filepath = self.filepath
        # Load the sequence names from the selected file
        action_names = []
        try:
            action_names = PsaReader().scan_sequence_names(self.filepath)
        except IOError:
            pass
        context.scene.psa_import.action_list.clear()
        for action_name in action_names:
            item = context.scene.psa_import.action_list.add()
            item.action_name = action_name.decode()
            item.is_selected = True
        return {'FINISHED'}
