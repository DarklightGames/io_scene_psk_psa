import os
from pathlib import Path
from typing import Iterable

from bpy.props import CollectionProperty, StringProperty
from bpy.types import Context, Event, FileHandler, Object, Operator, OperatorFileListElement
from bpy_extras.io_utils import ImportHelper

from .properties import PsaImportMixin, get_visible_sequences
from ..config import read_psa_config
from ..importer import PsaImportOptions, import_psa
from ..reader import PsaReader


def psa_import_poll(cls, context: Context):
    active_object = context.view_layer.objects.active
    if active_object is None or active_object.type != 'ARMATURE':
        cls.poll_message_set('The active object must be an armature')
        return False
    return True


class PSA_OT_import_sequences_select_from_text(Operator):
    bl_idname = 'psa.import_sequences_select_from_text'
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


class PSA_OT_import_sequences_select_all(Operator):
    bl_idname = 'psa.import_sequences_select_all'
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


class PSA_OT_import_sequences_deselect_all(Operator):
    bl_idname = 'psa.import_sequences_deselect_all'
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


class PSA_OT_import_drag_and_drop(Operator, PsaImportMixin):
    bl_idname = 'psa.import_drag_and_drop'
    bl_label = 'Import PSA'
    bl_description = 'Import multiple PSA files'
    bl_options = {'INTERNAL', 'UNDO', 'PRESET'}

    directory: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE', 'HIDDEN'})
    files: CollectionProperty(type=OperatorFileListElement, options={'SKIP_SAVE', 'HIDDEN'})

    def execute(self, context):
        warnings = []
        sequences_count = 0

        for file in self.files:
            psa_path = str(os.path.join(self.directory, file.name))
            psa_reader = PsaReader(psa_path)
            sequence_names = list(psa_reader.sequences.keys())
            options = psa_import_options_from_property_group(self, sequence_names)

            sequences_count += len(sequence_names)

            result = _import_psa(context, options, psa_path, context.view_layer.objects.active)
            warnings.extend(result.warnings)

        if len(warnings) > 0:
            message = f'Imported {sequences_count} action(s) from {len(self.files)} file(s) with {len(warnings)} warning(s)\n'
            self.report({'INFO'}, message)
            for warning in warnings:
                self.report({'WARNING'}, warning)

        self.report({'INFO'}, f'Imported {sequences_count} action(s) from {len(self.files)} file(s)')

        return {'FINISHED'}

    def invoke(self, context: Context, event):
        # Make sure the selected object is an obj.
        active_object = context.view_layer.objects.active
        if active_object is None or active_object.type != 'ARMATURE':
            self.report({'ERROR_INVALID_CONTEXT'}, 'The active object must be an armature')
            return {'CANCELLED'}

        # Show the import operator properties in a pop-up dialog (do not use the file selector).
        context.window_manager.invoke_props_dialog(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        draw_psa_import_options_no_panels(layout, self)


def psa_import_options_from_property_group(pg: PsaImportMixin, sequence_names: Iterable[str]) -> PsaImportOptions:
    options = PsaImportOptions()
    options.sequence_names = list(sequence_names)
    options.should_use_fake_user = pg.should_use_fake_user
    options.should_stash = pg.should_stash
    options.action_name_prefix = pg.action_name_prefix if pg.should_use_action_name_prefix else ''
    options.should_overwrite = pg.should_overwrite
    options.should_write_metadata = pg.should_write_metadata
    options.should_write_keyframes = pg.should_write_keyframes
    options.should_convert_to_samples = pg.should_convert_to_samples
    options.bone_mapping_mode = pg.bone_mapping_mode
    options.fps_source = pg.fps_source
    options.fps_custom = pg.fps_custom
    options.translation_scale = pg.translation_scale
    return options


def _import_psa(context,
                options: PsaImportOptions,
                filepath: str,
                armature_object: Object
                ):
    warnings = []

    if options.should_use_config_file:
        # Read the PSA config file if it exists.
        config_path = Path(filepath).with_suffix('.config')
        if config_path.exists():
            try:
                options.psa_config = read_psa_config(options.sequence_names, str(config_path))
            except Exception as e:
                warnings.append(f'Failed to read PSA config file: {e}')

    psa_reader = PsaReader(filepath)

    result = import_psa(context, psa_reader, armature_object, options)
    result.warnings.extend(warnings)

    return result


class PSA_OT_import_all(Operator, PsaImportMixin):
    bl_idname = 'psa.import_all'
    bl_label = 'Import PSA'
    bl_description = 'Import all sequences from the selected PSA file'
    bl_options = {'INTERNAL', 'UNDO'}

    filepath: StringProperty(
        name='File Path',
        description='File path used for importing the PSA file',
        maxlen=1024,
        default='',
        update=on_psa_file_path_updated)

    @classmethod
    def poll(cls, context):
        return psa_import_poll(cls, context)

    def execute(self, context):
        sequence_names = []
        with PsaReader(self.filepath) as psa_reader:
            sequence_names.extend(psa_reader.sequences.keys())

        options = PsaImportOptions(
            action_name_prefix=self.action_name_prefix,
            bone_mapping_mode=self.bone_mapping_mode,
            fps_custom=self.fps_custom,
            fps_source=self.fps_source,
            sequence_names=sequence_names,
            should_convert_to_samples=self.should_convert_to_samples,
            should_overwrite=self.should_overwrite,
            should_stash=self.should_stash,
            should_use_config_file=self.should_use_config_file,
            should_use_fake_user=self.should_use_fake_user,
            should_write_keyframes=self.should_write_keyframes,
            should_write_metadata=self.should_write_metadata,
            translation_scale=self.translation_scale
        )

        result = _import_psa(context, options, self.filepath, context.view_layer.objects.active)

        if len(result.warnings) > 0:
            message = f'Imported {len(options.sequence_names)} action(s) with {len(result.warnings)} warning(s)\n'
            self.report({'WARNING'}, message)
            for warning in result.warnings:
                self.report({'WARNING'}, warning)
        else:
            self.report({'INFO'}, f'Imported {len(options.sequence_names)} action(s)')

        return {'FINISHED'}

    def draw(self, context: Context):
        draw_psa_import_options_no_panels(self.layout, self)


class PSA_OT_import(Operator, ImportHelper, PsaImportMixin):
    bl_idname = 'psa.import_file'
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
        return psa_import_poll(cls, context)

    def execute(self, context):
        pg = getattr(context.scene, 'psa_import')
        options = psa_import_options_from_property_group(self, [x.action_name for x in pg.sequence_list if x.is_selected])

        if len(options.sequence_names) == 0:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No sequences selected')
            return {'CANCELLED'}

        result = _import_psa(context, options, self.filepath, context.view_layer.objects.active)

        if len(result.warnings) > 0:
            message = f'Imported {len(options.sequence_names)} action(s) with {len(result.warnings)} warning(s)\n'
            self.report({'WARNING'}, message)
            for warning in result.warnings:
                self.report({'WARNING'}, warning)
        else:
            self.report({'INFO'}, f'Imported {len(options.sequence_names)} action(s)')

        return {'FINISHED'}

    def invoke(self, context: Context, event: Event):
        # Attempt to load the PSA file for the pre-selected file.
        load_psa_file(context, self.filepath)

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context: Context):
        layout = self.layout
        pg = getattr(context.scene, 'psa_import')

        sequences_header, sequences_panel = layout.panel('sequences_panel_id', default_closed=False)
        sequences_header.label(text='Sequences')

        if sequences_panel:
            if pg.psa_error:
                row = sequences_panel.row()
                row.label(text='Select a PSA file', icon='ERROR')
            else:
                # Select buttons.
                rows = max(3, min(len(pg.sequence_list), 10))

                row = sequences_panel.row()
                col = row.column()

                row2 = col.row(align=True)
                row2.label(text='Select')
                row2.operator(PSA_OT_import_sequences_select_from_text.bl_idname, text='', icon='TEXT')
                row2.operator(PSA_OT_import_sequences_select_all.bl_idname, text='All', icon='CHECKBOX_HLT')
                row2.operator(PSA_OT_import_sequences_deselect_all.bl_idname, text='None', icon='CHECKBOX_DEHLT')

                col = col.row()
                col.template_list('PSA_UL_import_sequences', '', pg, 'sequence_list', pg, 'sequence_list_index', rows=rows)

            col = sequences_panel.column(heading='')
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, 'fps_source')
            if self.fps_source == 'CUSTOM':
                col.prop(self, 'fps_custom')
            col.prop(self, 'should_overwrite')
            col.prop(self, 'should_use_action_name_prefix')
            if self.should_use_action_name_prefix:
                col.prop(self, 'action_name_prefix')

        data_header, data_panel = layout.panel('data_panel_id', default_closed=False)
        data_header.label(text='Data')

        if data_panel:
            col = data_panel.column(heading='Write')
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, 'should_write_keyframes')
            col.prop(self, 'should_write_metadata')

            if self.should_write_keyframes:
                col = col.column(heading='Keyframes')
                col.use_property_split = True
                col.use_property_decorate = False
                col.prop(self, 'should_convert_to_samples')

        advanced_header, advanced_panel = layout.panel('advanced_panel_id', default_closed=True)
        advanced_header.label(text='Advanced')

        if advanced_panel:
            col = advanced_panel.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, 'bone_mapping_mode')

            col = advanced_panel.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, 'translation_scale', text='Translation Scale')

            col = advanced_panel.column(heading='Options')
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, 'should_use_fake_user')
            col.prop(self, 'should_stash')
            col.prop(self, 'should_use_config_file')


def draw_psa_import_options_no_panels(layout, pg: PsaImportMixin):
    col = layout.column(heading='Sequences')
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(pg, 'fps_source')
    if pg.fps_source == 'CUSTOM':
        col.prop(pg, 'fps_custom')
    col.prop(pg, 'should_overwrite')
    col.prop(pg, 'should_use_action_name_prefix')
    if pg.should_use_action_name_prefix:
        col.prop(pg, 'action_name_prefix')

    col = layout.column(heading='Write')
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(pg, 'should_write_keyframes')
    col.prop(pg, 'should_write_metadata')

    if pg.should_write_keyframes:
        col = col.column(heading='Keyframes')
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(pg, 'should_convert_to_samples')

    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(pg, 'bone_mapping_mode')
    col.prop(pg, 'translation_scale')

    col = layout.column(heading='Options')
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(pg, 'should_use_fake_user')
    col.prop(pg, 'should_stash')
    col.prop(pg, 'should_use_config_file')


class PSA_FH_import(FileHandler):  # TODO: rename and add handling for PSA export.
    bl_idname = 'PSA_FH_import'
    bl_label = 'File handler for Unreal PSA import'
    bl_import_operator = PSA_OT_import_drag_and_drop.bl_idname
    # bl_export_operator = 'psa_export.export'
    bl_file_extensions = '.psa'

    @classmethod
    def poll_drop(cls, context: Context):
        return context.area and context.area.type == 'VIEW_3D'


classes = (
    PSA_OT_import_sequences_select_all,
    PSA_OT_import_sequences_deselect_all,
    PSA_OT_import_sequences_select_from_text,
    PSA_OT_import,
    PSA_OT_import_all,
    PSA_OT_import_drag_and_drop,
    PSA_FH_import,
)
