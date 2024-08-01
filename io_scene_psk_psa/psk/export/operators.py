from typing import List

import bpy
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator, Context, Object
from bpy_extras.io_utils import ExportHelper

from .properties import object_eval_state_items
from ..builder import build_psk, PskBuildOptions, get_psk_input_objects_for_context, \
    get_psk_input_objects_for_collection
from ..writer import write_psk
from ...shared.helpers import populate_bone_collection_list


def is_bone_filter_mode_item_available(context, identifier):
    input_objects = get_psk_input_objects_for_context(context)
    armature_object = input_objects.armature_object
    if identifier == 'BONE_COLLECTIONS':
        if armature_object is None or armature_object.data is None or len(armature_object.data.collections) == 0:
            return False
    return True


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
    should_enforce_bone_name_restrictions: BoolProperty(
        default=False,
        name='Enforce Bone Name Restrictions',
        description='Enforce that bone names must only contain letters, numbers, spaces, hyphens and underscores.\n\n'
                    'Depending on the engine, improper bone names might not be referenced correctly by scripts'
    )

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection)

        try:
            input_objects = get_psk_input_objects_for_collection(collection)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        options = PskBuildOptions()
        options.bone_filter_mode = 'ALL'
        options.object_eval_state = self.object_eval_state
        options.materials = get_materials_for_mesh_objects(input_objects.mesh_objects)
        options.should_enforce_bone_name_restrictions = self.should_enforce_bone_name_restrictions

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

        # MESH
        mesh_header, mesh_panel = layout.panel('Mesh', default_closed=False)
        mesh_header.label(text='Mesh', icon='MESH_DATA')
        if mesh_panel:
            flow = mesh_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(self, 'object_eval_state', text='Data')

        # BONES
        bones_header, bones_panel = layout.panel('Bones', default_closed=False)
        bones_header.label(text='Bones', icon='BONE_DATA')
        if bones_panel:
            flow = bones_panel.grid_flow(row_major=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(self, 'should_enforce_bone_name_restrictions')


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

        pg = getattr(context.scene, 'psk_export')

        populate_bone_collection_list(input_objects.armature_object, pg.bone_collection_list)

        try:
            populate_material_list(input_objects.mesh_objects, pg.material_list)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    @classmethod
    def poll(cls, context):
        try:
            get_psk_input_objects_for_context(context)
        except RuntimeError as e:
            cls.poll_message_set(str(e))
            return False
        return True

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
            bone_filter_mode_items = pg.bl_rna.properties['bone_filter_mode'].enum_items_static
            row = bones_panel.row(align=True)
            for item in bone_filter_mode_items:
                identifier = item.identifier
                item_layout = row.row(align=True)
                item_layout.prop_enum(pg, 'bone_filter_mode', item.identifier)
                item_layout.enabled = is_bone_filter_mode_item_available(context, identifier)

            if pg.bone_filter_mode == 'BONE_COLLECTIONS':
                row = bones_panel.row()
                rows = max(3, min(len(pg.bone_collection_list), 10))
                row.template_list('PSX_UL_bone_collection_list', '', pg, 'bone_collection_list', pg, 'bone_collection_list_index', rows=rows)

            bones_panel.prop(pg, 'should_enforce_bone_name_restrictions')

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
        options.should_enforce_bone_name_restrictions = pg.should_enforce_bone_name_restrictions
        
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
)
