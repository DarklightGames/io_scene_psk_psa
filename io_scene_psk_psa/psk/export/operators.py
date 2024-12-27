from typing import List, Optional, cast, Iterable

import bpy
from bpy.props import StringProperty
from bpy.types import Operator, Context, Object, Collection, SpaceProperties, Depsgraph, Material
from bpy_extras.io_utils import ExportHelper

from .properties import add_psk_export_properties
from ..builder import build_psk, PskBuildOptions, get_psk_input_objects_for_context, \
    get_psk_input_objects_for_collection
from ..writer import write_psk
from ...shared.helpers import populate_bone_collection_list
from ...shared.ui import draw_bone_filter_mode


def get_materials_for_mesh_objects(depsgraph: Depsgraph, mesh_objects: Iterable[Object]):
    materials = []
    for mesh_object in mesh_objects:
        evaluated_mesh_object = mesh_object.evaluated_get(depsgraph)
        for i, material_slot in enumerate(evaluated_mesh_object.material_slots):
            material = material_slot.material
            if material is None:
                raise RuntimeError('Material slot cannot be empty (index ' + str(i) + ')')
            if material not in materials:
                materials.append(material)
    return materials


def populate_material_name_list(depsgraph: Depsgraph, mesh_objects, material_list):
    materials = get_materials_for_mesh_objects(depsgraph, mesh_objects)
    material_list.clear()
    for index, material in enumerate(materials):
        m = material_list.add()
        m.material_name = material.name
        m.index = index



def get_collection_from_context(context: Context) -> Optional[Collection]:
    if context.space_data.type != 'PROPERTIES':
        return None

    space_data = cast(SpaceProperties, context.space_data)

    if space_data.use_pin_id:
        return cast(Collection, space_data.pin_id)
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


class PSK_OT_populate_bone_collection_list(Operator):
    bl_idname = 'psk_export.populate_bone_collection_list'
    bl_label = 'Populate Bone Collection List'
    bl_description = 'Populate the bone collection list from the armature that will be used in this collection export'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        export_operator = get_collection_export_operator_from_context(context)
        if export_operator is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No valid export operator found in context')
            return {'CANCELLED'}
        input_objects = get_psk_input_objects_for_collection(context.collection)
        if input_objects.armature_object is None:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No armature found in collection')
            return {'CANCELLED'}
        populate_bone_collection_list(input_objects.armature_object, export_operator.bone_collection_list)
        return {'FINISHED'}


class PSK_OT_populate_material_name_list(Operator):
    bl_idname = 'psk_export.populate_material_name_list'
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
            populate_material_name_list(depsgraph, [x.obj for x in input_objects.mesh_objects], export_operator.material_name_list)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


class PSK_OT_material_list_move_up(Operator):
    bl_idname = 'psk_export.material_list_item_move_up'
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
    bl_idname = 'psk_export.material_list_item_move_down'
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
    bl_idname = 'psk_export.material_name_list_item_move_up'
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
    bl_idname = 'psk_export.material_name_list_item_move_down'
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


empty_set = set()


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


def get_psk_build_options_from_property_group(mesh_objects: Iterable[Object],  pg: 'PSK_PG_export', depsgraph: Optional[Depsgraph] = None) -> PskBuildOptions:
    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    options = PskBuildOptions()
    options.object_eval_state = pg.object_eval_state
    options.export_space = pg.export_space
    options.bone_filter_mode = pg.bone_filter_mode
    options.bone_collection_indices = [x.index for x in pg.bone_collection_list if x.is_selected]
    options.scale = pg.scale
    options.forward_axis = pg.forward_axis
    options.up_axis = pg.up_axis

    # TODO: perhaps move this into the build function and replace the materials list with a material names list.
    materials = get_materials_for_mesh_objects(depsgraph, mesh_objects)
    options.materials = get_sorted_materials_by_names(materials, [m.material_name for m in pg.material_name_list])

    return options


class PSK_OT_export_collection(Operator, ExportHelper):
    bl_idname = 'export.psk_collection'
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

        options = get_psk_build_options_from_property_group([x.obj for x in input_objects.mesh_objects], self)

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

    def draw(self, context: Context):
        layout = self.layout

        flow = layout.grid_flow(row_major=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        # MESH
        mesh_header, mesh_panel = layout.panel('Mesh', default_closed=False)
        mesh_header.label(text='Mesh', icon='MESH_DATA')
        if mesh_panel:
            flow = mesh_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(self, 'object_eval_state', text='Data')
            flow.prop(self, 'should_exclude_hidden_meshes')

        # BONES
        bones_header, bones_panel = layout.panel('Bones', default_closed=False)
        bones_header.label(text='Bones', icon='BONE_DATA')
        if bones_panel:
            draw_bone_filter_mode(bones_panel, self)
            if self.bone_filter_mode == 'BONE_COLLECTIONS':
                bones_panel.operator(PSK_OT_populate_bone_collection_list.bl_idname, icon='FILE_REFRESH')
                rows = max(3, min(len(self.bone_collection_list), 10))
                bones_panel.template_list('PSX_UL_bone_collection_list', '', self, 'bone_collection_list', self, 'bone_collection_list_index', rows=rows)

        # MATERIALS
        materials_header, materials_panel = layout.panel('Materials', default_closed=False)
        materials_header.label(text='Materials', icon='MATERIAL')

        if materials_panel:
            materials_panel.operator(PSK_OT_populate_material_name_list.bl_idname, icon='FILE_REFRESH')
            rows = max(3, min(len(self.material_name_list), 10))
            row = materials_panel.row()
            row.template_list('PSK_UL_material_names', '', self, 'material_name_list', self, 'material_name_list_index', rows=rows)
            col = row.column(align=True)
            col.operator(PSK_OT_material_list_name_move_up.bl_idname, text='', icon='TRIA_UP')
            col.operator(PSK_OT_material_list_name_move_down.bl_idname, text='', icon='TRIA_DOWN')

        # TRANSFORM
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



add_psk_export_properties(PSK_OT_export_collection)



class PSK_OT_export(Operator, ExportHelper):
    bl_idname = 'export.psk'
    bl_label = 'Export'
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = 'Export mesh and armature to PSK'
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

        if len(input_objects.mesh_objects) == 0:
            self.report({'ERROR_INVALID_CONTEXT'}, 'No mesh objects selected')
            return {'CANCELLED'}

        pg = getattr(context.scene, 'psk_export')

        populate_bone_collection_list(input_objects.armature_object, pg.bone_collection_list)

        depsgraph = context.evaluated_depsgraph_get()

        try:
            populate_material_name_list(depsgraph, [x.obj for x in input_objects.mesh_objects], pg.material_name_list)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout

        pg = getattr(context.scene, 'psk_export')

        # MESH
        mesh_header, mesh_panel = layout.panel('Mesh', default_closed=False)
        mesh_header.label(text='Mesh', icon='MESH_DATA')
        if mesh_panel:
            flow = mesh_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(pg, 'object_eval_state', text='Data')

        # BONES
        bones_header, bones_panel = layout.panel('Bones', default_closed=False)
        bones_header.label(text='Bones', icon='BONE_DATA')
        if bones_panel:
            draw_bone_filter_mode(bones_panel, pg)
            if pg.bone_filter_mode == 'BONE_COLLECTIONS':
                row = bones_panel.row()
                rows = max(3, min(len(pg.bone_collection_list), 10))
                row.template_list('PSX_UL_bone_collection_list', '', pg, 'bone_collection_list', pg, 'bone_collection_list_index', rows=rows)

        # MATERIALS
        materials_header, materials_panel = layout.panel('Materials', default_closed=False)
        materials_header.label(text='Materials', icon='MATERIAL')
        if materials_panel:
            row = materials_panel.row()
            rows = max(3, min(len(pg.bone_collection_list), 10))
            row.template_list('PSK_UL_material_names', '', pg, 'material_name_list', pg, 'material_name_list_index', rows=rows)
            col = row.column(align=True)
            col.operator(PSK_OT_material_list_move_up.bl_idname, text='', icon='TRIA_UP')
            col.operator(PSK_OT_material_list_move_down.bl_idname, text='', icon='TRIA_DOWN')

    def execute(self, context):
        pg = getattr(context.scene, 'psk_export')

        input_objects = get_psk_input_objects_for_context(context)
        options = get_psk_build_options_from_property_group([x.obj for x in input_objects.mesh_objects], pg)

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
    PSK_OT_populate_bone_collection_list,
    PSK_OT_populate_material_name_list,
    PSK_OT_material_list_name_move_up,
    PSK_OT_material_list_name_move_down,
)
