import os
import sys

from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from ..importer import PskImportOptions, import_psk
from ..reader import read_psk

empty_set = set()


class PSK_OT_import(Operator, ImportHelper):
    bl_idname = 'import_scene.psk'
    bl_label = 'Import'
    bl_options = {'INTERNAL', 'UNDO', 'PRESET'}
    __doc__ = 'Load a PSK file'
    filename_ext = '.psk'
    filter_glob: StringProperty(default='*.psk;*.pskx', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='')

    should_import_vertex_colors: BoolProperty(
        default=True,
        options=empty_set,
        name='Import Vertex Colors',
        description='Import vertex colors, if available'
    )
    vertex_color_space: EnumProperty(
        name='Vertex Color Space',
        options=empty_set,
        description='The source vertex color space',
        default='SRGBA',
        items=(
            ('LINEAR', 'Linear', ''),
            ('SRGBA', 'sRGBA', ''),
        )
    )
    should_import_vertex_normals: BoolProperty(
        default=True,
        name='Import Vertex Normals',
        options=empty_set,
        description='Import vertex normals, if available'
    )
    should_import_extra_uvs: BoolProperty(
        default=True,
        name='Import Extra UVs',
        options=empty_set,
        description='Import extra UV maps, if available'
    )
    should_import_mesh: BoolProperty(
        default=True,
        name='Import Mesh',
        options=empty_set,
        description='Import mesh'
    )
    should_import_materials: BoolProperty(
        default=True,
        name='Import Materials',
        options=empty_set,
    )
    should_import_skeleton: BoolProperty(
        default=True,
        name='Import Skeleton',
        options=empty_set,
        description='Import skeleton'
    )
    bone_length: FloatProperty(
        default=1.0,
        min=sys.float_info.epsilon,
        step=100,
        soft_min=1.0,
        name='Bone Length',
        options=empty_set,
        subtype='DISTANCE',
        description='Length of the bones'
    )
    should_import_shape_keys: BoolProperty(
        default=True,
        name='Import Shape Keys',
        options=empty_set,
        description='Import shape keys, if available'
    )
    scale: FloatProperty(
        name='Scale',
        default=1.0,
        soft_min=0.0,
    )

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

        layout.prop(self, 'should_import_mesh')

        if self.should_import_mesh:
            row = layout.row()
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

        layout.prop(self, 'should_import_skeleton')
        if self.should_import_skeleton:
            row = layout.row()
            col = row.column()
            col.use_property_split = True
            col.use_property_decorate = False
            col.prop(self, 'bone_length')


classes = (
    PSK_OT_import,
)
