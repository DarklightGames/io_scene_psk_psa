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
        name='Vertex Colors',
        description='Import vertex colors from PSKX files, if available'
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
        name='Vertex Normals',
        options=empty_set,
        description='Import vertex normals, if available'
    )
    should_import_extra_uvs: BoolProperty(
        default=True,
        name='Extra UVs',
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
    should_reuse_materials: BoolProperty(
        default=True,
        name='Reuse Materials',
        options=empty_set,
        description='Existing materials with matching names will be reused when available'
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
        description='Length of the bones'
    )
    should_import_shape_keys: BoolProperty(
        default=True,
        name='Shape Keys',
        options=empty_set,
        description='Import shape keys, if available'
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

        result = import_psk(psk, context, options)

        if len(result.warnings):
            message = f'PSK imported with {len(result.warnings)} warning(s)\n'
            message += '\n'.join(result.warnings)
            self.report({'WARNING'}, message)
        else:
            self.report({'INFO'}, f'PSK imported')

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'should_import_materials')
        layout.prop(self, 'should_import_mesh')
        row = layout.column()
        row.use_property_split = True
        row.use_property_decorate = False
        if self.should_import_mesh:
            row.prop(self, 'should_import_vertex_normals')
            row.prop(self, 'should_import_extra_uvs')
            row.prop(self, 'should_import_vertex_colors')
            if self.should_import_vertex_colors:
                row.prop(self, 'vertex_color_space')
            row.prop(self, 'should_import_shape_keys')
        layout.prop(self, 'should_import_skeleton')
        row = layout.column()
        row.use_property_split = True
        row.use_property_decorate = False
        if self.should_import_skeleton:
            row.prop(self, 'bone_length')


classes = (
    PSK_OT_import,
)
