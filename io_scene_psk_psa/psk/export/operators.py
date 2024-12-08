from typing import List, Optional, cast

import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatProperty, CollectionProperty, IntProperty
from bpy.types import Operator, Context, Object, Collection, SpaceProperties
from bpy_extras.io_utils import ExportHelper

from .properties import object_eval_state_items, export_space_items
from ..builder import build_psk, PskBuildOptions, get_psk_input_objects_for_context, \
    get_psk_input_objects_for_collection
from ..writer import write_psk
from ...shared.data import bone_filter_mode_items
from ...shared.helpers import populate_bone_collection_list
from ...shared.types import PSX_PG_bone_collection_list_item
from ...shared.ui import draw_bone_filter_mode


def get_materials_for_mesh_objects(mesh_objects: List[Object]):
    materials = []
    for mesh_object in mesh_objects:
        for i, material_slot in enumerate(mesh_object.material_slots):
            material = material_slot.material
            if material is None:
                raise RuntimeError('Material slot cannot be empty (index ' + str(i) + ')')
            if material not in materials:
                materials.append(material)
    return materials


def populate_material_list(mesh_objects, material_list):
    materials =  get_materials_for_mesh_objects(mesh_objects)
    material_list.clear()
    for index, material in enumerate(materials):
        m = material_list.add()
        m.material = material
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


class PSK_OT_material_list_move_up(Operator):
    bl_idname = 'psk_export.material_list_item_move_up'
    bl_label = 'Move Up'
    bl_options = {'INTERNAL'}
    bl_description = 'Move the selected material up one slot'

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psk_export')
        return pg.material_list_index > 0

    def execute(self, context):
        pg = getattr(context.scene, 'psk_export')
        pg.material_list.move(pg.material_list_index, pg.material_list_index - 1)
        pg.material_list_index -= 1
        return {'FINISHED'}


class PSK_OT_material_list_move_down(Operator):
    bl_idname = 'psk_export.material_list_item_move_down'
    bl_label = 'Move Down'
    bl_options = {'INTERNAL'}
    bl_description = 'Move the selected material down one slot'

    @classmethod
    def poll(cls, context):
        pg = getattr(context.scene, 'psk_export')
        return pg.material_list_index < len(pg.material_list) - 1

    def execute(self, context):
        pg = getattr(context.scene, 'psk_export')
        pg.material_list.move(pg.material_list_index, pg.material_list_index + 1)
        pg.material_list_index += 1
        return {'FINISHED'}


empty_set = set()

axis_identifiers = ('X', 'Y', 'Z', '-X', '-Y', '-Z')

forward_items = (
    ('X', 'X Forward', ''),
    ('Y', 'Y Forward', ''),
    ('Z', 'Z Forward', ''),
    ('-X', '-X Forward', ''),
    ('-Y', '-Y Forward', ''),
    ('-Z', '-Z Forward', ''),
)

up_items = (
    ('X', 'X Up', ''),
    ('Y', 'Y Up', ''),
    ('Z', 'Z Up', ''),
    ('-X', '-X Up', ''),
    ('-Y', '-Y Up', ''),
    ('-Z', '-Z Up', ''),
)

def forward_axis_update(self, context):
    if self.forward_axis == self.up_axis:
        # Automatically set the up axis to the next available axis
        self.up_axis = next((axis for axis in axis_identifiers if axis != self.forward_axis), 'Z')


def up_axis_update(self, context):
    if self.up_axis == self.forward_axis:
        # Automatically set the forward axis to the next available axis
        self.forward_axis = next((axis for axis in axis_identifiers if axis != self.up_axis), 'X')

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

    object_eval_state: EnumProperty(
        items=object_eval_state_items,
        name='Object Evaluation State',
        default='EVALUATED'
    )
    should_exclude_hidden_meshes: BoolProperty(
        default=False,
        name='Visible Only',
        description='Export only visible meshes'
    )
    scale: FloatProperty(
        name='Scale',
        default=1.0,
        description='Scale factor to apply to the exported mesh and armature',
        min=0.0001,
        soft_max=100.0
    )
    export_space: EnumProperty(
        name='Export Space',
        description='Space to export the mesh in',
        items=export_space_items,
        default='WORLD'
    )
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        options=empty_set,
        description='',
        items=bone_filter_mode_items,
    )
    bone_collection_list: CollectionProperty(type=PSX_PG_bone_collection_list_item)
    bone_collection_list_index: IntProperty(default=0)
    forward_axis: EnumProperty(
        name='Forward',
        items=forward_items,
        default='X',
        update=forward_axis_update
    )
    up_axis: EnumProperty(
        name='Up',
        items=up_items,
        default='Z',
        update=up_axis_update
    )

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection)

        try:
            input_objects = get_psk_input_objects_for_collection(collection, self.should_exclude_hidden_meshes)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        options = PskBuildOptions()
        options.object_eval_state = self.object_eval_state
        options.materials = get_materials_for_mesh_objects([x.obj for x in input_objects.mesh_objects])
        options.scale = self.scale
        options.export_space = self.export_space
        options.bone_filter_mode = self.bone_filter_mode
        options.bone_collection_indices = [x.index for x in self.bone_collection_list if x.is_selected]
        options.forward_axis = self.forward_axis
        options.up_axis = self.up_axis

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
            bones_panel.operator(PSK_OT_populate_bone_collection_list.bl_idname, icon='FILE_REFRESH')
            draw_bone_filter_mode(bones_panel, self)
            if self.bone_filter_mode == 'BONE_COLLECTIONS':
                rows = max(3, min(len(self.bone_collection_list), 10))
                bones_panel.template_list('PSX_UL_bone_collection_list', '', self, 'bone_collection_list', self, 'bone_collection_list_index', rows=rows)

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

        try:
            populate_material_list([x.obj for x in input_objects.mesh_objects], pg.material_list)
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
            row.template_list('PSK_UL_materials', '', pg, 'material_list', pg, 'material_list_index', rows=rows)
            col = row.column(align=True)
            col.operator(PSK_OT_material_list_move_up.bl_idname, text='', icon='TRIA_UP')
            col.operator(PSK_OT_material_list_move_down.bl_idname, text='', icon='TRIA_DOWN')

    def execute(self, context):
        pg = getattr(context.scene, 'psk_export')

        input_objects = get_psk_input_objects_for_context(context)

        options = PskBuildOptions()
        options.bone_filter_mode = pg.bone_filter_mode
        options.bone_collection_indices = [x.index for x in pg.bone_collection_list if x.is_selected]
        options.object_eval_state = pg.object_eval_state
        options.materials = [m.material for m in pg.material_list]
        options.scale = pg.scale
        options.export_space = pg.export_space
        
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
)
