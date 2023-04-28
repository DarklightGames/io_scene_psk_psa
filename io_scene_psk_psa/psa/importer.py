import fnmatch
import os
import re
import typing
from collections import Counter
from typing import List, Optional

import bpy
import numpy
from bpy.props import StringProperty, BoolProperty, CollectionProperty, PointerProperty, IntProperty, EnumProperty
from bpy.types import Operator, UIList, PropertyGroup, FCurve
from bpy_extras.io_utils import ImportHelper
from mathutils import Vector, Quaternion

from .data import Psa
from .reader import PsaReader


class PsaImportOptions(object):
    def __init__(self):
        self.should_use_fake_user = False
        self.should_stash = False
        self.sequence_names = []
        self.should_overwrite = False
        self.should_write_keyframes = True
        self.should_write_metadata = True
        self.action_name_prefix = ''
        self.should_convert_to_samples = False
        self.bone_mapping_mode = 'CASE_INSENSITIVE'


class ImportBone(object):
    def __init__(self, psa_bone: Psa.Bone):
        self.psa_bone: Psa.Bone = psa_bone
        self.parent: Optional[ImportBone] = None
        self.armature_bone = None
        self.pose_bone = None
        self.orig_loc: Vector = Vector()
        self.orig_quat: Quaternion = Quaternion()
        self.post_quat: Quaternion = Quaternion()
        self.fcurves: List[FCurve] = []


def calculate_fcurve_data(import_bone: ImportBone, key_data: typing.Iterable[float]):
    # Convert world-space transforms to local-space transforms.
    key_rotation = Quaternion(key_data[0:4])
    key_location = Vector(key_data[4:])
    q = import_bone.post_quat.copy()
    q.rotate(import_bone.orig_quat)
    quat = q
    q = import_bone.post_quat.copy()
    if import_bone.parent is None:
        q.rotate(key_rotation.conjugated())
    else:
        q.rotate(key_rotation)
    quat.rotate(q.conjugated())
    loc = key_location - import_bone.orig_loc
    loc.rotate(import_bone.post_quat.conjugated())
    return quat.w, quat.x, quat.y, quat.z, loc.x, loc.y, loc.z


class PsaImportResult:
    def __init__(self):
        self.warnings: List[str] = []


def import_psa(psa_reader: PsaReader, armature_object: bpy.types.Object, options: PsaImportOptions) -> PsaImportResult:
    result = PsaImportResult()
    sequences = map(lambda x: psa_reader.sequences[x], options.sequence_names)
    armature_data = typing.cast(bpy.types.Armature, armature_object.data)

    # Create an index mapping from bones in the PSA to bones in the target armature.
    psa_to_armature_bone_indices = {}
    armature_bone_names = [x.name for x in armature_data.bones]
    psa_bone_names = []
    for psa_bone_index, psa_bone in enumerate(psa_reader.bones):
        psa_bone_name: str = psa_bone.name.decode('windows-1252')
        try:
            psa_to_armature_bone_indices[psa_bone_index] = armature_bone_names.index(psa_bone_name)
        except ValueError:
            # PSA bone could not be mapped directly to an armature bone by name.
            # Attempt to create a bone mapping by ignoring the case of the names.
            if options.bone_mapping_mode == 'CASE_INSENSITIVE':
                for armature_bone_index, armature_bone_name in enumerate(armature_bone_names):
                    if armature_bone_name.upper() == psa_bone_name.upper():
                        psa_to_armature_bone_indices[psa_bone_index] = armature_bone_index
                        psa_bone_name = armature_bone_name
                        break
        psa_bone_names.append(psa_bone_name)

    # Remove ambiguous bone mappings (where multiple PSA bones correspond to the same armature bone).
    armature_bone_index_counts = Counter(psa_to_armature_bone_indices.values())
    for armature_bone_index, count in armature_bone_index_counts.items():
        if count > 1:
            psa_bone_indices = []
            for psa_bone_index, mapped_bone_index in psa_to_armature_bone_indices:
                if mapped_bone_index == armature_bone_index:
                    psa_bone_indices.append(psa_bone_index)
            ambiguous_psa_bone_names = list(sorted([psa_bone_names[x] for x in psa_bone_indices]))
            result.warnings.append(
                f'Ambiguous mapping for bone {armature_bone_names[armature_bone_index]}!\n'
                f'The following PSA bones all map to the same armature bone: {ambiguous_psa_bone_names}\n'
                f'These bones will be ignored.'
            )

    # Report if there are missing bones in the target armature.
    missing_bone_names = set(psa_bone_names).difference(set(armature_bone_names))
    if len(missing_bone_names) > 0:
        result.warnings.append(
            f'The armature \'{armature_object.name}\' is missing {len(missing_bone_names)} bones that exist in '
            'the PSA:\n' +
            str(list(sorted(missing_bone_names)))
        )
    del armature_bone_names

    # Create intermediate bone data for import operations.
    import_bones = []
    import_bones_dict = dict()

    for (psa_bone_index, psa_bone), psa_bone_name in zip(enumerate(psa_reader.bones), psa_bone_names):
        if psa_bone_index not in psa_to_armature_bone_indices:
            # PSA bone does not map to armature bone, skip it and leave an empty bone in its place.
            import_bones.append(None)
            continue
        import_bone = ImportBone(psa_bone)
        import_bone.armature_bone = armature_data.bones[psa_bone_name]
        import_bone.pose_bone = armature_object.pose.bones[psa_bone_name]
        import_bones_dict[psa_bone_name] = import_bone
        import_bones.append(import_bone)

    for import_bone in filter(lambda x: x is not None, import_bones):
        armature_bone = import_bone.armature_bone
        if armature_bone.parent is not None and armature_bone.parent.name in psa_bone_names:
            import_bone.parent = import_bones_dict[armature_bone.parent.name]
        # Calculate the original location & rotation of each bone (in world-space maybe?)
        if armature_bone.get('orig_quat') is not None:
            # TODO: ideally we don't rely on bone auxiliary data like this, the non-aux data path is incorrect
            # (animations are flipped 180 around Z)
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
    actions = []
    for sequence in sequences:
        # Add the action.
        sequence_name = sequence.name.decode('windows-1252')
        action_name = options.action_name_prefix + sequence_name

        if options.should_overwrite and action_name in bpy.data.actions:
            action = bpy.data.actions[action_name]
        else:
            action = bpy.data.actions.new(name=action_name)

        if options.should_write_keyframes:
            # Remove existing f-curves (replace with action.fcurves.clear() in Blender 3.2)
            while len(action.fcurves) > 0:
                action.fcurves.remove(action.fcurves[-1])

            # Create f-curves for the rotation and location of each bone.
            for psa_bone_index, armature_bone_index in psa_to_armature_bone_indices.items():
                import_bone = import_bones[psa_bone_index]
                pose_bone = import_bone.pose_bone
                rotation_data_path = pose_bone.path_from_id('rotation_quaternion')
                location_data_path = pose_bone.path_from_id('location')
                import_bone.fcurves = [
                    action.fcurves.new(rotation_data_path, index=0, action_group=pose_bone.name),  # Qw
                    action.fcurves.new(rotation_data_path, index=1, action_group=pose_bone.name),  # Qx
                    action.fcurves.new(rotation_data_path, index=2, action_group=pose_bone.name),  # Qy
                    action.fcurves.new(rotation_data_path, index=3, action_group=pose_bone.name),  # Qz
                    action.fcurves.new(location_data_path, index=0, action_group=pose_bone.name),  # Lx
                    action.fcurves.new(location_data_path, index=1, action_group=pose_bone.name),  # Ly
                    action.fcurves.new(location_data_path, index=2, action_group=pose_bone.name),  # Lz
                ]

            # Read the sequence data matrix from the PSA.
            sequence_data_matrix = psa_reader.read_sequence_data_matrix(sequence_name)

            # Convert the sequence's data from world-space to local-space.
            for bone_index, import_bone in enumerate(import_bones):
                if import_bone is None:
                    continue
                for frame_index in range(sequence.frame_count):
                    # This bone has writeable keyframes for this frame.
                    key_data = sequence_data_matrix[frame_index, bone_index]
                    # Calculate the local-space key data for the bone.
                    sequence_data_matrix[frame_index, bone_index] = calculate_fcurve_data(import_bone, key_data)

            # Write the keyframes out.
            fcurve_data = numpy.zeros(2 * sequence.frame_count, dtype=float)
            fcurve_data[0::2] = range(sequence.frame_count)
            for bone_index, import_bone in enumerate(import_bones):
                if import_bone is None:
                    continue
                for fcurve_index, fcurve in enumerate(import_bone.fcurves):
                    fcurve_data[1::2] = sequence_data_matrix[:, bone_index, fcurve_index]
                    fcurve.keyframe_points.add(sequence.frame_count)
                    fcurve.keyframe_points.foreach_set('co', fcurve_data)

            if options.should_convert_to_samples:
                # Bake the curve to samples.
                for fcurve in action.fcurves:
                    fcurve.convert_to_samples(start=0, end=sequence.frame_count)

        # Write meta-data.
        if options.should_write_metadata:
            action['psa_sequence_fps'] = sequence.fps

        action.use_fake_user = options.should_use_fake_user

        actions.append(action)

    # If the user specifies, store the new animations as strips on a non-contributing NLA track.
    if options.should_stash:
        if armature_object.animation_data is None:
            armature_object.animation_data_create()
        for action in actions:
            nla_track = armature_object.animation_data.nla_tracks.new()
            nla_track.name = action.name
            nla_track.mute = True
            nla_track.strips.new(name=action.name, start=0, action=action)

    return result


empty_set = set()


class PsaImportActionListItem(PropertyGroup):
    action_name: StringProperty(options=empty_set)
    is_selected: BoolProperty(default=False, options=empty_set)


def load_psa_file(context, filepath: str):
    pg = context.scene.psa_import
    pg.sequence_list.clear()
    pg.psa.bones.clear()
    pg.psa_error = ''
    try:
        # Read the file and populate the action list.
        p = os.path.abspath(filepath)
        psa_reader = PsaReader(p)
        for sequence in psa_reader.sequences.values():
            item = pg.sequence_list.add()
            item.action_name = sequence.name.decode('windows-1252')
        for psa_bone in psa_reader.bones:
            item = pg.psa.bones.add()
            item.bone_name = psa_bone.name.decode('windows-1252')
    except Exception as e:
        pg.psa_error = str(e)


def on_psa_file_path_updated(cls, context):
    load_psa_file(context, cls.filepath)


class PsaBonePropertyGroup(PropertyGroup):
    bone_name: StringProperty(options=empty_set)


class PsaDataPropertyGroup(PropertyGroup):
    bones: CollectionProperty(type=PsaBonePropertyGroup)
    sequence_count: IntProperty(default=0)


class PsaImportPropertyGroup(PropertyGroup):
    psa_error: StringProperty(default='')
    psa: PointerProperty(type=PsaDataPropertyGroup)
    sequence_list: CollectionProperty(type=PsaImportActionListItem)
    sequence_list_index: IntProperty(name='', default=0)
    should_use_fake_user: BoolProperty(default=True, name='Fake User',
                                       description='Assign each imported action a fake user so that the data block is '
                                                   'saved even it has no users',
                                       options=empty_set)
    should_stash: BoolProperty(default=False, name='Stash',
                               description='Stash each imported action as a strip on a new non-contributing NLA track',
                               options=empty_set)
    should_use_action_name_prefix: BoolProperty(default=False, name='Prefix Action Name', options=empty_set)
    action_name_prefix: StringProperty(default='', name='Prefix', options=empty_set)
    should_overwrite: BoolProperty(default=False, name='Overwrite', options=empty_set,
                                   description='If an action with a matching name already exists, the existing action '
                                               'will have it\'s data overwritten instead of a new action being created')
    should_write_keyframes: BoolProperty(default=True, name='Keyframes', options=empty_set)
    should_write_metadata: BoolProperty(default=True, name='Metadata', options=empty_set,
                                        description='Additional data will be written to the custom properties of the '
                                                    'Action (e.g., frame rate)')
    sequence_filter_name: StringProperty(default='', options={'TEXTEDIT_UPDATE'})
    sequence_filter_is_selected: BoolProperty(default=False, options=empty_set, name='Only Show Selected',
                                              description='Only show selected sequences')
    sequence_use_filter_invert: BoolProperty(default=False, options=empty_set)
    sequence_use_filter_regex: BoolProperty(default=False, name='Regular Expression',
                                            description='Filter using regular expressions', options=empty_set)
    select_text: PointerProperty(type=bpy.types.Text)
    should_convert_to_samples: BoolProperty(
        default=False,
        name='Convert to Samples',
        description='Convert keyframes to read-only samples. '
                    'Recommended if you do not plan on editing the actions directly'
    )
    bone_mapping_mode: EnumProperty(
        name='Bone Mapping',
        options=empty_set,
        description='The method by which bones from the incoming PSA file are mapped to the armature',
        items=(
            ('EXACT', 'Exact', 'Bone names must match exactly.', 'EXACT', 0),
            ('CASE_INSENSITIVE', 'Case Insensitive', 'Bones names must match, ignoring case (e.g., the bone PSA bone '
             '\'root\' can be mapped to the armature bone \'Root\')', 'CASE_INSENSITIVE', 1),
        )
    )


def filter_sequences(pg: PsaImportPropertyGroup, sequences) -> List[int]:
    bitflag_filter_item = 1 << 30
    flt_flags = [bitflag_filter_item] * len(sequences)

    if pg.sequence_filter_name is not None:
        # Filter name is non-empty.
        if pg.sequence_use_filter_regex:
            # Use regular expression. If regex pattern doesn't compile, just ignore it.
            try:
                regex = re.compile(pg.sequence_filter_name)
                for i, sequence in enumerate(sequences):
                    if not regex.match(sequence.action_name):
                        flt_flags[i] &= ~bitflag_filter_item
            except re.error:
                pass
        else:
            # User regular text matching.
            for i, sequence in enumerate(sequences):
                if not fnmatch.fnmatch(sequence.action_name, f'*{pg.sequence_filter_name}*'):
                    flt_flags[i] &= ~bitflag_filter_item

    if pg.sequence_filter_is_selected:
        for i, sequence in enumerate(sequences):
            if not sequence.is_selected:
                flt_flags[i] &= ~bitflag_filter_item

    if pg.sequence_use_filter_invert:
        # Invert filter flags for all items.
        for i, sequence in enumerate(sequences):
            flt_flags[i] ^= bitflag_filter_item

    return flt_flags


def get_visible_sequences(pg: PsaImportPropertyGroup, sequences) -> List[PsaImportActionListItem]:
    bitflag_filter_item = 1 << 30
    visible_sequences = []
    for i, flag in enumerate(filter_sequences(pg, sequences)):
        if bool(flag & bitflag_filter_item):
            visible_sequences.append(sequences[i])
    return visible_sequences


class PSA_UL_SequenceList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index, flt_flag):
        row = layout.row(align=True)
        split = row.split(align=True, factor=0.75)
        column = split.row(align=True)
        column.alignment = 'LEFT'
        column.prop(item, 'is_selected', icon_only=True)
        column.label(text=getattr(item, 'action_name'))

    def draw_filter(self, context, layout):
        pg = getattr(context.scene, 'psa_import')
        row = layout.row()
        sub_row = row.row(align=True)
        sub_row.prop(pg, 'sequence_filter_name', text="")
        sub_row.prop(pg, 'sequence_use_filter_invert', text="", icon='ARROW_LEFTRIGHT')
        sub_row.prop(pg, 'sequence_use_filter_regex', text="", icon='SORTBYEXT')
        sub_row.prop(pg, 'sequence_filter_is_selected', text="", icon='CHECKBOX_HLT')

    def filter_items(self, context, data, property_):
        pg = getattr(context.scene, 'psa_import')
        sequences = getattr(data, property_)
        flt_flags = filter_sequences(pg, sequences)
        flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(sequences, 'action_name')
        return flt_flags, flt_neworder


class PSA_UL_ImportSequenceList(PSA_UL_SequenceList, UIList):
    pass


class PSA_UL_ImportActionList(PSA_UL_SequenceList, UIList):
    pass


class PsaImportSequencesFromText(Operator):
    bl_idname = 'psa_import.sequences_select_from_text'
    bl_label = 'Select By Text List'
    bl_description = 'Select sequences by name from text list'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psa_import')
        return len(pg.sequence_list) > 0

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=256)

    def draw(self, context):
        layout = self.layout
        pg = getattr(context.scene, 'psa_import')
        layout.label(icon='INFO', text='Each sequence name should be on a new line.')
        layout.prop(pg, 'select_text', text='')

    def execute(self, context):
        pg = getattr(context.scene, 'psa_import')
        if pg.select_text is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No text block selected')
            return {'CANCELLED'}
        contents = pg.select_text.as_string()
        count = 0
        for line in contents.split('\n'):
            for sequence in pg.sequence_list:
                if sequence.action_name == line:
                    sequence.is_selected = True
                    count += 1
        self.report({'INFO'}, f'Selected {count} sequence(s)')
        return {'FINISHED'}


class PsaImportSequencesSelectAll(Operator):
    bl_idname = 'psa_import.sequences_select_all'
    bl_label = 'All'
    bl_description = 'Select all sequences'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psa_import')
        visible_sequences = get_visible_sequences(pg, pg.sequence_list)
        has_unselected_actions = any(map(lambda action: not action.is_selected, visible_sequences))
        return len(visible_sequences) > 0 and has_unselected_actions

    def execute(self, context):
        pg = getattr(context.scene, 'psa_import')
        visible_sequences = get_visible_sequences(pg, pg.sequence_list)
        for sequence in visible_sequences:
            sequence.is_selected = True
        return {'FINISHED'}


class PsaImportSequencesDeselectAll(Operator):
    bl_idname = 'psa_import.sequences_deselect_all'
    bl_label = 'None'
    bl_description = 'Deselect all visible sequences'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psa_import')
        visible_sequences = get_visible_sequences(pg, pg.sequence_list)
        has_selected_sequences = any(map(lambda sequence: sequence.is_selected, visible_sequences))
        return len(visible_sequences) > 0 and has_selected_sequences

    def execute(self, context):
        pg = getattr(context.scene, 'psa_import')
        visible_sequences = get_visible_sequences(pg, pg.sequence_list)
        for sequence in visible_sequences:
            sequence.is_selected = False
        return {'FINISHED'}


class PsaImportSelectFile(Operator):
    bl_idname = 'psa_import.select_file'
    bl_label = 'Select'
    bl_options = {'INTERNAL'}
    bl_description = 'Select a PSA file from which to import animations'
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.psa", options={'HIDDEN'})

    def execute(self, context):
        getattr(context.scene, 'psa_import').psa_file_path = self.filepath
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PsaImportOperator(Operator, ImportHelper):
    bl_idname = 'psa_import.import'
    bl_label = 'Import'
    bl_description = 'Import the selected animations into the scene as actions'
    bl_options = {'INTERNAL', 'UNDO'}

    filename_ext = '.psa'
    filter_glob: StringProperty(default='*.psa', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for importing the PSA file',
        maxlen=1024,
        default='',
        update=on_psa_file_path_updated)

    @classmethod
    def poll(cls, context):
        active_object = context.view_layer.objects.active
        if active_object is None or active_object.type != 'ARMATURE':
            cls.poll_message_set('The active object must be an armature')
            return False
        return True

    def execute(self, context):
        pg = getattr(context.scene, 'psa_import')
        psa_reader = PsaReader(self.filepath)
        sequence_names = [x.action_name for x in pg.sequence_list if x.is_selected]

        options = PsaImportOptions()
        options.sequence_names = sequence_names
        options.should_use_fake_user = pg.should_use_fake_user
        options.should_stash = pg.should_stash
        options.action_name_prefix = pg.action_name_prefix if pg.should_use_action_name_prefix else ''
        options.should_overwrite = pg.should_overwrite
        options.should_write_metadata = pg.should_write_metadata
        options.should_write_keyframes = pg.should_write_keyframes
        options.should_convert_to_samples = pg.should_convert_to_samples
        options.bone_mapping_mode = pg.bone_mapping_mode

        result = import_psa(psa_reader, context.view_layer.objects.active, options)

        if len(result.warnings) > 0:
            message = f'Imported {len(sequence_names)} action(s) with {len(result.warnings)} warning(s)\n'
            message += '\n'.join(result.warnings)
            self.report({'WARNING'}, message)
        else:
            self.report({'INFO'}, f'Imported {len(sequence_names)} action(s)')

        return {'FINISHED'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        # Attempt to load the PSA file for the pre-selected file.
        load_psa_file(context, self.filepath)

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        pg = getattr(context.scene, 'psa_import')

        if pg.psa_error:
            row = layout.row()
            row.label(text='Select a PSA file', icon='ERROR')
        else:
            box = layout.box()

            box.label(text=f'Sequences ({len(pg.sequence_list)})', icon='ARMATURE_DATA')

            # Select buttons.
            rows = max(3, min(len(pg.sequence_list), 10))

            row = box.row()
            col = row.column()

            row2 = col.row(align=True)
            row2.label(text='Select')
            row2.operator(PsaImportSequencesFromText.bl_idname, text='', icon='TEXT')
            row2.operator(PsaImportSequencesSelectAll.bl_idname, text='All', icon='CHECKBOX_HLT')
            row2.operator(PsaImportSequencesDeselectAll.bl_idname, text='None', icon='CHECKBOX_DEHLT')

            col = col.row()
            col.template_list('PSA_UL_ImportSequenceList', '', pg, 'sequence_list', pg, 'sequence_list_index', rows=rows)

        col = layout.column(heading='')
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(pg, 'should_overwrite')

        col = layout.column(heading='Write')
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(pg, 'should_write_keyframes')
        col.prop(pg, 'should_write_metadata')

        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(pg, 'bone_mapping_mode')

        if pg.should_write_keyframes:
            col = layout.column(heading='Keyframes')
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(pg, 'should_convert_to_samples')
            col.separator()

        col = layout.column(heading='Options')
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(pg, 'should_use_fake_user')
        col.prop(pg, 'should_stash')
        col.prop(pg, 'should_use_action_name_prefix')

        if pg.should_use_action_name_prefix:
            col.prop(pg, 'action_name_prefix')


classes = (
    PsaImportActionListItem,
    PsaBonePropertyGroup,
    PsaDataPropertyGroup,
    PsaImportPropertyGroup,
    PSA_UL_SequenceList,
    PSA_UL_ImportSequenceList,
    PSA_UL_ImportActionList,
    PsaImportSequencesSelectAll,
    PsaImportSequencesDeselectAll,
    PsaImportSequencesFromText,
    PsaImportOperator,
    PsaImportSelectFile,
)
