from pathlib import Path
from typing import Iterable, List, Optional, cast as typing_cast

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Collection, Context, Depsgraph, Material, Object, Operator, SpaceProperties
from bpy_extras.io_utils import ExportHelper

from .properties import PskExportMixin
from ..builder import (
    PskBuildOptions,
    build_psk,
    get_materials_for_mesh_objects,
    get_psk_input_objects_for_collection,
    get_psk_input_objects_for_context,
)
from ..writer import write_psk
from ...shared.helpers import populate_bone_collection_list
from ...shared.ui import draw_bone_filter_mode


def populate_material_name_list(depsgraph: Depsgraph, mesh_objects: Iterable[Object], material_list):
    materials = list(get_materials_for_mesh_objects(depsgraph, mesh_objects))

    # Order the mesh object materials by the order any existing entries in the material list.
    # This way, if the user has already set up the material list, we don't change the order.
    material_names = [x.material_name for x in material_list]
    materials = get_sorted_materials_by_names(materials, material_names)

    material_list.clear()
    for index, material in enumerate(materials):
        m = material_list.add()
        m.material_name = material.name
        m.index = index



def get_collection_from_context(context: Context) -> Optional[Collection]:
    if context.space_data.type != 'PROPERTIES':
        return None

    space_data = typing_cast(SpaceProperties, context.space_data)

    if space_data.use_pin_id:
        return typing_cast(Collection, space_data.pin_id)
    else:
        return context.collection


def get_collection_export_operator_from_context(context: Context) -> Optional[object]:
    collection = get_collection_from_context(context)
    if collection is None:
        return None
    if 0 > collection.active_exporter_index >= len(collection.exporters):
        return None
    exporter = collection.exporters[collection.active_exporter_index]
    # TODO: make sure this is actually an ASE exporter.
    return exporter.export_properties


class PSK_OT_bone_collection_list_populate(Operator):
    bl_idname = 'psk.bone_collection_list_populate'
    bl_label = 'Populate Bone Collection List'
    bl_description = 'Populate the bone collection list from the armature that will be used in this collection export'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No valid export operator found in context')
            return {'CANCELLED'}
        try:
            input_objects = get_psk_input_objects_for_collection(context.collection)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}
        if not input_objects.armature_objects:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No armature modifiers found on mesh objects')
            return {'CANCELLED'}
        populate_bone_collection_list(input_objects.armature_objects, export_operator.bone_collection_list)
        return {'FINISHED'}


class PSK_OT_bone_collection_list_select_all(Operator):
    bl_idname = 'psk.bone_collection_list_select_all'
    bl_label = 'Select All'
    bl_description = 'Select all bone collections'
    bl_options = {'INTERNAL'}

    is_selected: BoolProperty(default=True)

    def execute(self, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No valid export operator found in context')
            return {'CANCELLED'}
        for item in export_operator.bone_collection_list:
            item.is_selected = self.is_selected
        return {'FINISHED'}


class PSK_OT_populate_material_name_list(Operator):
    bl_idname = 'psk.export_populate_material_name_list'
    bl_label = 'Populate Material Name List'
    bl_description = 'Populate the material name list from the objects that will be used in this export'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No valid export operator found in context')
            return {'CANCELLED'}
        depsgraph = context.evaluated_depsgraph_get()
        input_objects = get_psk_input_objects_for_collection(context.collection)
        try:
            populate_material_name_list(depsgraph, [x.obj for x in input_objects.mesh_dfs_objects], export_operator.material_name_list)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}



def material_list_names_search_cb(self, context: Context, edit_text: str):
    for material in bpy.data.materials:
        yield material.name


class PSK_OT_material_list_name_add(Operator):
    bl_idname = 'psk.export_material_name_list_item_add'
    bl_label = 'Add Material'
    bl_description = 'Add a material to the material name list (useful if you want to add a material slot that is not actually used in the mesh)'
    bl_options = {'INTERNAL'}

    name: StringProperty(search=material_list_names_search_cb, name='Material Name', default='None')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No valid export operator found in context')
            return {'CANCELLED'}
        m = export_operator.material_name_list.add()
        m.material_name = self.name
        m.index = len(export_operator.material_name_list) - 1
        return {'FINISHED'}



class PSK_OT_material_list_move_up(Operator):
    bl_idname = 'psk.export_material_list_item_move_up'
    bl_label = 'Move Up'
    bl_options = {'INTERNAL'}
    bl_description = 'Move the selected material up one slot'

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psk_export')
        return pg.material_name_list_index > 0

    def execute(self, context):
        pg = getattr(context.scene, 'psk_export')
        pg.material_name_list.move(pg.material_name_list_index, pg.material_name_list_index - 1)
        pg.material_name_list_index -= 1
        return {'FINISHED'}


class PSK_OT_material_list_move_down(Operator):
    bl_idname = 'psk.export_material_list_item_move_down'
    bl_label = 'Move Down'
    bl_options = {'INTERNAL'}
    bl_description = 'Move the selected material down one slot'

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psk_export')
        return pg.material_name_list_index < len(pg.material_name_list) - 1

    def execute(self, context):
        pg = getattr(context.scene, 'psk_export')
        pg.material_name_list.move(pg.material_name_list_index, pg.material_name_list_index + 1)
        pg.material_name_list_index += 1
        return {'FINISHED'}


class PSK_OT_material_list_name_move_up(Operator):
    bl_idname = 'psk.export_material_name_list_item_move_up'
    bl_label = 'Move Up'
    bl_options = {'INTERNAL'}
    bl_description = 'Move the selected material name up one slot'

    @classmethod
    def poll(cls, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            return False
        return export_operator.material_name_list_index > 0

    def execute(self, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No valid export operator found in context')
            return {'CANCELLED'}
        export_operator.material_name_list.move(export_operator.material_name_list_index, export_operator.material_name_list_index - 1)
        export_operator.material_name_list_index -= 1
        return {'FINISHED'}


class PSK_OT_material_list_name_move_down(Operator):
    bl_idname = 'psk.export_material_name_list_item_move_down'
    bl_label = 'Move Down'
    bl_options = {'INTERNAL'}
    bl_description = 'Move the selected material name down one slot'

    @classmethod
    def poll(cls, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            return False
        return export_operator.material_name_list_index < len(export_operator.material_name_list) - 1

    def execute(self, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No valid export operator found in context')
            return {'CANCELLED'}
        export_operator.material_name_list.move(export_operator.material_name_list_index, export_operator.material_name_list_index + 1)
        export_operator.material_name_list_index += 1
        return {'FINISHED'}


def get_sorted_materials_by_names(materials: Iterable[Material], material_names: List[str]) -> List[Material]:
    """
    Sorts the materials by the order of the material names list. Any materials not in the list will be appended to the
    end of the list in the order they are found.

    @param materials: A list of materials to sort
    @param material_names: A list of material names to sort by
    @return: A sorted list of materials
    """
    materials_in_collection = [m for m in materials if m.name in material_names]
    materials_not_in_collection = [m for m in materials if m.name not in material_names]
    materials_in_collection = sorted(materials_in_collection, key=lambda x: material_names.index(x.name))
    return materials_in_collection + materials_not_in_collection


def get_psk_build_options_from_property_group(pg: PskExportMixin) -> PskBuildOptions:
    options = PskBuildOptions()
    options.object_eval_state = pg.object_eval_state
    options.export_space = pg.export_space
    options.bone_filter_mode = pg.bone_filter_mode
    options.bone_collection_indices = [(x.armature_object_name, x.index) for x in pg.bone_collection_list if x.is_selected]
    options.scale = pg.scale
    options.forward_axis = pg.forward_axis
    options.up_axis = pg.up_axis
    options.root_bone_name = pg.root_bone_name
    options.material_order_mode = pg.material_order_mode
    options.material_name_list = pg.material_name_list
    return options


class PSK_OT_export_collection(Operator, ExportHelper, PskExportMixin):
    bl_idname = 'psk.export_collection'
    bl_label = 'Export'
    bl_options = {'INTERNAL'}
    filename_ext = '.psk'
    filter_glob: StringProperty(default='*.psk', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='',
        subtype='FILE_PATH')
    collection: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection)

        try:
            input_objects = get_psk_input_objects_for_collection(collection, self.should_exclude_hidden_meshes)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        options = get_psk_build_options_from_property_group(self)
        filepath = str(Path(self.filepath).resolve())

        try:
            result = build_psk(context, input_objects, options)
            for warning in result.warnings:
                self.report({'WARNING'}, warning)
            write_psk(result.psk, filepath)
            if len(result.warnings) > 0:
                self.report({'WARNING'}, f'PSK export successful with {len(result.warnings)} warnings')
            else:
                self.report({'INFO'}, f'PSK export successful')
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        return {'FINISHED'}

    def draw(self, context: Context):
        layout = self.layout

        flow = layout.grid_flow(row_major=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        # Mesh
        mesh_header, mesh_panel = layout.panel('Mesh', default_closed=False)
        mesh_header.label(text='Mesh', icon='MESH_DATA')
        if mesh_panel:
            flow = mesh_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(self, 'object_eval_state', text='Data')
            flow.prop(self, 'should_exclude_hidden_meshes')

        # Bones
        bones_header, bones_panel = layout.panel('Bones', default_closed=False)
        bones_header.label(text='Bones', icon='BONE_DATA')
        if bones_panel:
            draw_bone_filter_mode(bones_panel, self, True)

            if self.bone_filter_mode == 'BONE_COLLECTIONS':
                row = bones_panel.row()
                rows = max(3, min(len(self.bone_collection_list), 10))
                row.template_list('PSX_UL_bone_collection_list', '', self, 'bone_collection_list', self, 'bone_collection_list_index', rows=rows)
                col = row.column(align=True)
                col.operator(PSK_OT_bone_collection_list_populate.bl_idname, text='', icon='FILE_REFRESH')
                col.separator()
                op = col.operator(PSK_OT_bone_collection_list_select_all.bl_idname, text='', icon='CHECKBOX_HLT')
                op.is_selected = True
                op = col.operator(PSK_OT_bone_collection_list_select_all.bl_idname, text='', icon='CHECKBOX_DEHLT')
                op.is_selected = False

            advanced_bones_header, advanced_bones_panel = bones_panel.panel('Advanced', default_closed=True)
            advanced_bones_header.label(text='Advanced')
            if advanced_bones_panel:
                flow = advanced_bones_panel.grid_flow(row_major=True)
                flow.use_property_split = True
                flow.use_property_decorate = False
                flow.prop(self, 'root_bone_name')

        # Materials
        materials_header, materials_panel = layout.panel('Materials', default_closed=False)
        materials_header.label(text='Materials', icon='MATERIAL')

        if materials_panel:
            flow = materials_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(self, 'material_order_mode', text='Material Order')

            if self.material_order_mode == 'MANUAL':
                rows = max(3, min(len(self.material_name_list), 10))
                row = materials_panel.row()
                row.template_list('PSK_UL_material_names', '', self, 'material_name_list', self, 'material_name_list_index', rows=rows)
                col = row.column(align=True)
                col.operator(PSK_OT_populate_material_name_list.bl_idname, text='', icon='FILE_REFRESH')
                col.separator()
                col.operator(PSK_OT_material_list_name_move_up.bl_idname, text='', icon='TRIA_UP')
                col.operator(PSK_OT_material_list_name_move_down.bl_idname, text='', icon='TRIA_DOWN')
                col.separator()
                col.operator(PSK_OT_material_list_name_add.bl_idname, text='', icon='ADD')

        # Transform
        transform_header, transform_panel = layout.panel('Transform', default_closed=False)
        transform_header.label(text='Transform')
        if transform_panel:
            flow = transform_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(self, 'export_space')
            flow.prop(self, 'scale')
            flow.prop(self, 'forward_axis')
            flow.prop(self, 'up_axis')



class PSK_OT_export(Operator, ExportHelper):
    bl_idname = 'psk.export'
    bl_label = 'Export'
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = 'Export selected meshes to PSK'
    filename_ext = '.psk'
    filter_glob: StringProperty(default='*.psk', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='')

    def invoke(self, context, event):
        try:
            input_objects = get_psk_input_objects_for_context(context)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        pg = getattr(context.scene, 'psk_export')

        populate_bone_collection_list(input_objects.armature_objects, pg.bone_collection_list)

        depsgraph = context.evaluated_depsgraph_get()

        try:
            populate_material_name_list(depsgraph, [x.obj for x in input_objects.mesh_dfs_objects], pg.material_name_list)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout

        pg = getattr(context.scene, 'psk_export')

        # Mesh
        mesh_header, mesh_panel = layout.panel('Mesh', default_closed=False)
        mesh_header.label(text='Mesh', icon='MESH_DATA')
        if mesh_panel:
            flow = mesh_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'object_eval_state', text='Data')

        # Bones
        bones_header, bones_panel = layout.panel('Bones', default_closed=False)
        bones_header.label(text='Bones', icon='BONE_DATA')
        if bones_panel:
            draw_bone_filter_mode(bones_panel, pg)
            if pg.bone_filter_mode == 'BONE_COLLECTIONS':
                row = bones_panel.row()
                rows = max(3, min(len(pg.bone_collection_list), 10))
                row.template_list('PSX_UL_bone_collection_list', '', pg, 'bone_collection_list', pg, 'bone_collection_list_index', rows=rows)
            bones_advanced_header, bones_advanced_panel = bones_panel.panel('Advanced', default_closed=True)
            bones_advanced_header.label(text='Advanced')
            if bones_advanced_panel:
                flow = bones_advanced_panel.grid_flow(row_major=True)
                flow.use_property_split = True
                flow.use_property_decorate = False
                flow.prop(pg, 'root_bone_name')

        # Materials
        materials_header, materials_panel = layout.panel('Materials', default_closed=False)
        materials_header.label(text='Materials', icon='MATERIAL')
        if materials_panel:
            flow = materials_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'material_order_mode', text='Material Order')

            if pg.material_order_mode == 'MANUAL':
                row = materials_panel.row()
                rows = max(3, min(len(pg.bone_collection_list), 10))
                row.template_list('PSK_UL_material_names', '', pg, 'material_name_list', pg, 'material_name_list_index', rows=rows)
                col = row.column(align=True)
                col.operator(PSK_OT_material_list_move_up.bl_idname, text='', icon='TRIA_UP')
                col.operator(PSK_OT_material_list_move_down.bl_idname, text='', icon='TRIA_DOWN')

        # Transform
        transform_header, transform_panel = layout.panel('Transform', default_closed=False)
        transform_header.label(text='Transform')
        if transform_panel:
            flow = transform_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'export_space')
            flow.prop(pg, 'scale')
            flow.prop(pg, 'forward_axis')
            flow.prop(pg, 'up_axis')

    def execute(self, context):
        pg = getattr(context.scene, 'psk_export')

        input_objects = get_psk_input_objects_for_context(context)
        options = get_psk_build_options_from_property_group(pg)

        try:
            result = build_psk(context, input_objects, options)
            for warning in result.warnings:
                self.report({'WARNING'}, warning)
            write_psk(result.psk, self.filepath)
            if len(result.warnings) > 0:
                self.report({'WARNING'}, f'PSK export successful with {len(result.warnings)} warnings')
            else:
                self.report({'INFO'}, f'PSK export successful')
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        return {'FINISHED'}


classes = (
    PSK_OT_material_list_move_up,
    PSK_OT_material_list_move_down,
    PSK_OT_export,
    PSK_OT_export_collection,
    PSK_OT_bone_collection_list_populate,
    PSK_OT_bone_collection_list_select_all,
    PSK_OT_populate_material_name_list,
    PSK_OT_material_list_name_move_up,
    PSK_OT_material_list_name_move_down,
    PSK_OT_material_list_name_add,
)
