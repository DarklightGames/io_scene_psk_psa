import bpy
import mathutils
from mathutils import Vector, Quaternion, Matrix
from .data import Psa
from typing import List, AnyStr, Optional
import bpy
from bpy.types import Operator, Action, UIList, PropertyGroup, Panel, Armature, FileSelectParams
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy.props import StringProperty, BoolProperty, CollectionProperty, PointerProperty, IntProperty
from .reader import PsaReader
import numpy as np


class PsaImporter(object):
    def __init__(self):
        pass

    def import_psa(self, psa_reader: PsaReader, sequence_names: List[AnyStr], context):
        psa = psa_reader.psa
        properties = context.scene.psa_import
        sequences = map(lambda x: psa.sequences[x], sequence_names)
        armature_object = properties.armature_object
        armature_data = armature_object.data

        class ImportBone(object):
            def __init__(self, psa_bone: Psa.Bone):
                self.psa_bone: Psa.Bone = psa_bone
                self.parent: Optional[ImportBone] = None
                self.armature_bone = None
                self.pose_bone = None
                self.orig_loc: Vector = Vector()
                self.orig_quat: Quaternion = Quaternion()
                self.post_quat: Quaternion = Quaternion()
                self.fcurves = []

        # create an index mapping from bones in the PSA to bones in the target armature.
        psa_to_armature_bone_indices = {}
        armature_bone_names = [x.name for x in armature_data.bones]
        psa_bone_names = []
        for psa_bone_index, psa_bone in enumerate(psa.bones):
            psa_bone_name = psa_bone.name.decode('windows-1252')
            psa_bone_names.append(psa_bone_name)
            try:
                psa_to_armature_bone_indices[psa_bone_index] = armature_bone_names.index(psa_bone_name)
            except ValueError:
                pass

        # report if there are missing bones in the target armature
        missing_bone_names = set(psa_bone_names).difference(set(armature_bone_names))
        if len(missing_bone_names) > 0:
            print(f'The armature object \'{armature_object.name}\' is missing the following bones that exist in the PSA:')
            print(list(sorted(missing_bone_names)))
        del armature_bone_names

        # Create intermediate bone data for import operations.
        import_bones = []
        import_bones_dict = dict()

        for psa_bone_index, psa_bone in enumerate(psa.bones):
            bone_name = psa_bone.name.decode('windows-1252')
            if psa_bone_index not in psa_to_armature_bone_indices:  # TODO: replace with bone_name in armature_data.bones
                # PSA bone does not map to armature bone, skip it and leave an empty bone in its place.
                import_bones.append(None)
                continue
            import_bone = ImportBone(psa_bone)
            import_bone.armature_bone = armature_data.bones[bone_name]
            import_bone.pose_bone = armature_object.pose.bones[bone_name]
            import_bones_dict[bone_name] = import_bone
            import_bones.append(import_bone)

        for import_bone in filter(lambda x: x is not None, import_bones):
            armature_bone = import_bone.armature_bone
            if armature_bone.parent is not None and armature_bone.parent.name in psa_bone_names:
                import_bone.parent = import_bones_dict[armature_bone.parent.name]
            # Calculate the original location & rotation of each bone (in world-space maybe?)
            if armature_bone.get('orig_quat') is not None:
                # TODO: ideally we don't rely on bone auxiliary data like this, the non-aux data path is incorrect (animations are flipped 180 around Z)
                import_bone.orig_quat = Quaternion(armature_bone['orig_quat'])
                import_bone.orig_loc = Vector(armature_bone['orig_loc'])
                import_bone.post_quat = Quaternion(armature_bone['post_quat'])
            else:
                if import_bone.parent is not None:
                    import_bone.orig_loc = armature_bone.matrix_local.translation - armature_bone.parent.matrix_local.translation
                    import_bone.orig_loc.rotate(armature_bone.parent.matrix_local.to_quaternion().conjugated())
                    import_bone.orig_quat = armature_bone.matrix_local.to_quaternion()
                    import_bone.orig_quat.rotate(armature_bone.parent.matrix_local.to_quaternion().conjugated())
                    import_bone.orig_quat.conjugate()
                else:
                    import_bone.orig_loc = armature_bone.matrix_local.translation.copy()
                    import_bone.orig_quat = armature_bone.matrix_local.to_quaternion()
                import_bone.post_quat = import_bone.orig_quat.conjugated()

        # Create and populate the data for new sequences.
        for sequence in sequences:
            action = bpy.data.actions.new(name=sequence.name.decode())
            for psa_bone_index, armature_bone_index in psa_to_armature_bone_indices.items():
                import_bone = import_bones[psa_bone_index]
                pose_bone = import_bone.pose_bone

                # create fcurves from rotation and location data
                rotation_data_path = pose_bone.path_from_id('rotation_quaternion')
                location_data_path = pose_bone.path_from_id('location')
                import_bone.fcurves.extend([
                    action.fcurves.new(rotation_data_path, index=0),  # Qw
                    action.fcurves.new(rotation_data_path, index=1),  # Qx
                    action.fcurves.new(rotation_data_path, index=2),  # Qy
                    action.fcurves.new(rotation_data_path, index=3),  # Qz
                    action.fcurves.new(location_data_path, index=0),  # Lx
                    action.fcurves.new(location_data_path, index=1),  # Ly
                    action.fcurves.new(location_data_path, index=2),  # Lz
                ])

            key_index = 0

            # Read the sequence keys from the PSA file.
            sequence_name = sequence.name.decode('windows-1252')
            sequence_keys = psa_reader.read_sequence_keys(sequence_name)

            for frame_index in range(sequence.frame_count):
                for bone_index, import_bone in enumerate(import_bones):
                    if import_bone is None:
                        # bone does not exist in the armature, skip it
                        key_index += 1
                        continue

                    # Convert world-space transforms to local-space transforms.
                    key_rotation = Quaternion(tuple(sequence_keys[key_index].rotation))
                    q = import_bone.post_quat.copy()
                    q.rotate(import_bone.orig_quat)
                    quat = q
                    q = import_bone.post_quat.copy()
                    if import_bone.parent is None:
                        q.rotate(key_rotation.conjugated())
                    else:
                        q.rotate(key_rotation)
                    quat.rotate(q.conjugated())

                    key_location = Vector(tuple(sequence_keys[key_index].location))
                    loc = key_location - import_bone.orig_loc
                    loc.rotate(import_bone.post_quat.conjugated())

                    bone_fcurve_data = quat.w, quat.x, quat.y, quat.z, loc.x, loc.y, loc.z
                    for fcurve, datum in zip(import_bone.fcurves, bone_fcurve_data):
                        fcurve.keyframe_points.insert(frame_index, datum)

                    key_index += 1


class PsaImportActionListItem(PropertyGroup):
    action_name: StringProperty()
    frame_count: IntProperty()
    is_selected: BoolProperty(default=False)

    @property
    def name(self):
        return self.action_name


def on_psa_filepath_updated(property, context):
    context.scene.psa_import.action_list.clear()
    try:
        # Read the file and populate the action list.
        psa = PsaReader(context.scene.psa_import.psa_filepath).psa
        for sequence in psa.sequences.values():
            item = context.scene.psa_import.action_list.add()
            item.action_name = sequence.name.decode('windows-1252')
            item.frame_count = sequence.frame_count
            item.is_selected = True
    except IOError:
        # TODO: set an error somewhere so the user knows the PSA could not be read.
        pass


class PsaImportPropertyGroup(bpy.types.PropertyGroup):
    psa_filepath: StringProperty(default='', subtype='FILE_PATH', update=on_psa_filepath_updated)
    armature_object: PointerProperty(name='Armature', type=bpy.types.Object)
    action_list: CollectionProperty(type=PsaImportActionListItem)
    action_list_index: IntProperty(name='', default=0)
    action_filter_name: StringProperty(default='')


class PSA_UL_ImportActionList(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        split = row.split(align=True, factor=0.75)
        action_col = split.row(align=True)
        action_col.alignment = 'LEFT'
        action_col.prop(item, 'is_selected', icon_only=True)
        action_col.label(text=item.action_name)

    def draw_filter(self, context, layout):
        row = layout.row()
        subrow = row.row(align=True)
        subrow.prop(self, 'filter_name', text="")
        subrow.prop(self, 'use_filter_invert', text="", icon='ARROW_LEFTRIGHT')
        subrow = row.row(align=True)
        subrow.prop(self, 'use_filter_sort_reverse', text='', icon='SORT_ASC')

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


class PsaImportSelectAll(bpy.types.Operator):
    bl_idname = 'psa_import.actions_select_all'
    bl_label = 'All'

    @classmethod
    def poll(cls, context):
        action_list = context.scene.psa_import.action_list
        has_unselected_actions = any(map(lambda action: not action.is_selected, action_list))
        return len(action_list) > 0 and has_unselected_actions

    def execute(self, context):
        for action in context.scene.psa_import.action_list:
            action.is_selected = True
        return {'FINISHED'}


class PsaImportDeselectAll(bpy.types.Operator):
    bl_idname = 'psa_import.actions_deselect_all'
    bl_label = 'None'

    @classmethod
    def poll(cls, context):
        action_list = context.scene.psa_import.action_list
        has_selected_actions = any(map(lambda action: action.is_selected, action_list))
        return len(action_list) > 0 and has_selected_actions

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
        row.prop(scene.psa_import, 'psa_filepath', text='PSA File')
        row = layout.row()
        row.prop_search(scene.psa_import, 'armature_object', bpy.data, 'objects')
        box = layout.box()
        box.label(text=f'Actions ({len(scene.psa_import.action_list)})', icon='ACTION')
        row = box.row()
        rows = max(3, min(len(scene.psa_import.action_list), 10))
        row.template_list('PSA_UL_ImportActionList', 'asd', scene.psa_import, 'action_list', scene.psa_import, 'action_list_index', rows=rows)
        row = box.row(align=True)
        row.label(text='Select')
        row.operator('psa_import.actions_select_all', text='All')
        row.operator('psa_import.actions_deselect_all', text='None')
        layout.operator('psa_import.import', text=f'Import')


class PsaImportOperator(Operator):
    bl_idname = 'psa_import.import'
    bl_label = 'Import'

    @classmethod
    def poll(cls, context):
        action_list = context.scene.psa_import.action_list
        has_selected_actions = any(map(lambda action: action.is_selected, action_list))
        armature_object = context.scene.psa_import.armature_object
        return has_selected_actions and armature_object is not None

    def execute(self, context):
        psa_reader = PsaReader(context.scene.psa_import.psa_filepath)
        sequence_names = [x.action_name for x in context.scene.psa_import.action_list if x.is_selected]
        PsaImporter().import_psa(psa_reader, sequence_names, context)
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
        context.scene.psa_import.psa_filepath = self.filepath
        # Load the sequence names from the selected file
        return {'FINISHED'}
