import bpy
import mathutils
from mathutils import Vector, Quaternion, Matrix
from .data import Psa
from typing import List, AnyStr, Optional
import bpy
from bpy.types import Operator, Action, UIList, PropertyGroup, Panel, Armature
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy.props import StringProperty, BoolProperty, CollectionProperty, PointerProperty, IntProperty
from .reader import PsaReader


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
                # TODO: this is UGLY, come up with a way to just map indices for these
                self.fcurve_quat_w = None
                self.fcurve_quat_x = None
                self.fcurve_quat_y = None
                self.fcurve_quat_z = None
                self.fcurve_location_x = None
                self.fcurve_location_y = None
                self.fcurve_location_z = None

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

                # rotation
                rotation_data_path = pose_bone.path_from_id('rotation_quaternion')
                import_bone.fcurve_quat_w = action.fcurves.new(rotation_data_path, index=0)
                import_bone.fcurve_quat_x = action.fcurves.new(rotation_data_path, index=1)
                import_bone.fcurve_quat_y = action.fcurves.new(rotation_data_path, index=2)
                import_bone.fcurve_quat_z = action.fcurves.new(rotation_data_path, index=3)

                # location
                location_data_path = pose_bone.path_from_id('location')
                import_bone.fcurve_location_x = action.fcurves.new(location_data_path, index=0)
                import_bone.fcurve_location_y = action.fcurves.new(location_data_path, index=1)
                import_bone.fcurve_location_z = action.fcurves.new(location_data_path, index=2)

                # add keyframes
                import_bone.fcurve_quat_w.keyframe_points.add(sequence.frame_count)
                import_bone.fcurve_quat_x.keyframe_points.add(sequence.frame_count)
                import_bone.fcurve_quat_y.keyframe_points.add(sequence.frame_count)
                import_bone.fcurve_quat_z.keyframe_points.add(sequence.frame_count)
                import_bone.fcurve_location_x.keyframe_points.add(sequence.frame_count)
                import_bone.fcurve_location_y.keyframe_points.add(sequence.frame_count)
                import_bone.fcurve_location_z.keyframe_points.add(sequence.frame_count)

            should_invert_root = False
            key_index = 0
            sequence_name = sequence.name.decode('windows-1252')
            sequence_keys = psa_reader.get_sequence_keys(sequence_name)

            for frame_index in range(sequence.frame_count):
                for import_bone in import_bones:
                    if import_bone is None:
                        # bone does not exist in the armature, skip it
                        key_index += 1
                        continue

                    key_location = Vector(tuple(sequence_keys[key_index].location))
                    key_rotation = Quaternion(tuple(sequence_keys[key_index].rotation))

                    q = import_bone.post_quat.copy()
                    q.rotate(import_bone.orig_quat)
                    quat = q
                    q = import_bone.post_quat.copy()
                    if import_bone.parent is None and not should_invert_root:
                        q.rotate(key_rotation.conjugated())
                    else:
                        q.rotate(key_rotation)
                    quat.rotate(q.conjugated())

                    loc = key_location - import_bone.orig_loc
                    loc.rotate(import_bone.post_quat.conjugated())

                    import_bone.fcurve_quat_w.keyframe_points[frame_index].co = frame_index, quat.w
                    import_bone.fcurve_quat_x.keyframe_points[frame_index].co = frame_index, quat.x
                    import_bone.fcurve_quat_y.keyframe_points[frame_index].co = frame_index, quat.y
                    import_bone.fcurve_quat_z.keyframe_points[frame_index].co = frame_index, quat.z
                    import_bone.fcurve_location_x.keyframe_points[frame_index].co = frame_index, loc.x
                    import_bone.fcurve_location_y.keyframe_points[frame_index].co = frame_index, loc.y
                    import_bone.fcurve_location_z.keyframe_points[frame_index].co = frame_index, loc.z

                    key_index += 1


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
        psa_reader = PsaReader(context.scene.psa_import.cool_filepath)
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
        context.scene.psa_import.cool_filepath = self.filepath
        # Load the sequence names from the selected file
        sequence_names = []
        try:
            sequence_names = PsaReader.scan_sequence_names(self.filepath)
        except IOError:
            pass
        context.scene.psa_import.action_list.clear()
        for sequence_name in sequence_names:
            item = context.scene.psa_import.action_list.add()
            item.action_name = sequence_name.decode('windows-1252')
            item.is_selected = True
        return {'FINISHED'}
