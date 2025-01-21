import os

from bpy.props import StringProperty
from bpy.types import Operator, FileHandler, Context
from bpy_extras.io_utils import ImportHelper

from ..importer import PskImportOptions, import_psk
from ..properties import PskImportMixin
from ..reader import read_psk

empty_set = set()


class PSK_OT_import(Operator, ImportHelper, PskImportMixin):
    bl_idname = 'psk.import'
    bl_label = 'Import'
    bl_options = {'INTERNAL', 'UNDO', 'PRESET'}
    bl_description = 'Import a PSK file'
    filename_ext = '.psk'
    filter_glob: StringProperty(default='*.psk;*.pskx', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='')

    def execute(self, context):
        psk = read_psk(self.filepath)

        options = PskImportOptions()
        options.name = os.path.splitext(os.path.basename(self.filepath))[0]
        options.should_import_mesh = self.should_import_mesh
        options.should_import_extra_uvs = self.should_import_extra_uvs
        options.should_import_vertex_colors = self.should_import_vertex_colors
        options.should_import_vertex_normals = self.should_import_vertex_normals
        options.vertex_color_space = self.vertex_color_space
        options.should_import_skeleton = self.should_import_skeleton
        options.bone_length = self.bone_length
        options.should_import_materials = self.should_import_materials
        options.should_import_shape_keys = self.should_import_shape_keys
        options.scale = self.scale

        if self.bdk_repository_id:
            options.bdk_repository_id = self.bdk_repository_id

        if not options.should_import_mesh and not options.should_import_skeleton:
            self.report({'ERROR'}, 'Nothing to import')
            return {'CANCELLED'}

        result = import_psk(psk, context, options)

        if len(result.warnings):
            message = f'PSK imported with {len(result.warnings)} warning(s)\n'
            message += '\n'.join(result.warnings)
            self.report({'WARNING'}, message)
        else:
            self.report({'INFO'}, f'PSK imported ({options.name})')

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout

        row = layout.row()

        col = row.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(self, 'scale')

        mesh_header, mesh_panel = layout.panel('mesh_panel_id', default_closed=False)
        mesh_header.prop(self, 'should_import_mesh')

        if mesh_panel and self.should_import_mesh:
            row = mesh_panel.row()
            col = row.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, 'should_import_materials', text='Materials')
            col.prop(self, 'should_import_vertex_normals', text='Vertex Normals')
            col.prop(self, 'should_import_extra_uvs', text='Extra UVs')
            col.prop(self, 'should_import_vertex_colors', text='Vertex Colors')
            if self.should_import_vertex_colors:
                col.prop(self, 'vertex_color_space')
            col.prop(self, 'should_import_shape_keys', text='Shape Keys')

        skeleton_header, skeleton_panel = layout.panel('skeleton_panel_id', default_closed=False)
        skeleton_header.prop(self, 'should_import_skeleton')

        if skeleton_panel and self.should_import_skeleton:
            row = skeleton_panel.row()
            col = row.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, 'bone_length')


# TODO: move to another file
class PSK_FH_import(FileHandler):
    bl_idname = 'PSK_FH_import'
    bl_label = 'Unreal PSK'
    bl_import_operator = PSK_OT_import.bl_idname
    bl_export_operator = 'psk.export_collection'
    bl_file_extensions = '.psk;.pskx'

    @classmethod
    def poll_drop(cls, context: Context):
        return context.area and context.area.type == 'VIEW_3D'

classes = (
    PSK_OT_import,
    PSK_FH_import,
)
