from .data import *
from ..types import BoneGroupListItem
from ..helpers import populate_bone_group_list
from .builder import PskBuilder, PskBuilderOptions
from typing import Type
from bpy.types import Operator, PropertyGroup
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, CollectionProperty, IntProperty, BoolProperty, EnumProperty

MAX_WEDGE_COUNT = 65536
MAX_POINT_COUNT = 4294967296
MAX_BONE_COUNT = 256
MAX_MATERIAL_COUNT = 256


class PskExporter(object):

    def __init__(self, psk: Psk):
        self.psk: Psk = psk

    @staticmethod
    def write_section(fp, name: bytes, data_type: Type[Structure] = None, data: list = None):
        section = Section()
        section.name = name
        if data_type is not None and data is not None:
            section.data_size = sizeof(data_type)
            section.data_count = len(data)
        fp.write(section)
        if data is not None:
            for datum in data:
                fp.write(datum)

    def export(self, path: str):
        if len(self.psk.wedges) > MAX_WEDGE_COUNT:
            raise RuntimeError(f'Number of wedges ({len(self.psk.wedges)}) exceeds limit of {MAX_WEDGE_COUNT}')
        if len(self.psk.bones) > MAX_BONE_COUNT:
            raise RuntimeError(f'Number of bones ({len(self.psk.bones)}) exceeds limit of {MAX_BONE_COUNT}')
        if len(self.psk.points) > MAX_POINT_COUNT:
            raise RuntimeError(f'Numbers of vertices ({len(self.psk.points)}) exceeds limit of {MAX_POINT_COUNT}')
        if len(self.psk.materials) > MAX_MATERIAL_COUNT:
            raise RuntimeError(f'Number of materials ({len(self.psk.materials)}) exceeds limit of {MAX_MATERIAL_COUNT}')

        with open(path, 'wb') as fp:
            self.write_section(fp, b'ACTRHEAD')
            self.write_section(fp, b'PNTS0000', Vector3, self.psk.points)

            wedges = []
            for index, w in enumerate(self.psk.wedges):
                wedge = Psk.Wedge16()
                wedge.material_index = w.material_index
                wedge.u = w.u
                wedge.v = w.v
                wedge.point_index = w.point_index
                wedges.append(wedge)

            self.write_section(fp, b'VTXW0000', Psk.Wedge16, wedges)
            self.write_section(fp, b'FACE0000', Psk.Face, self.psk.faces)
            self.write_section(fp, b'MATT0000', Psk.Material, self.psk.materials)
            self.write_section(fp, b'REFSKELT', Psk.Bone, self.psk.bones)
            self.write_section(fp, b'RAWWEIGHTS', Psk.Weight, self.psk.weights)


def is_bone_filter_mode_item_available(context, identifier):
    input_objects = PskBuilder.get_input_objects(context)
    armature_object = input_objects.armature_object
    if identifier == 'BONE_GROUPS':
        if not armature_object or not armature_object.pose or not armature_object.pose.bone_groups:
            return False
    # else if... you can set up other conditions if you add more options
    return True


class PskExportOperator(Operator, ExportHelper):
    bl_idname = 'export.psk'
    bl_label = 'Export'
    bl_options = {'INTERNAL', 'UNDO'}
    __doc__ = 'Export mesh and armature to PSK'
    filename_ext = '.psk'
    filter_glob: StringProperty(default='*.psk', options={'HIDDEN'})

    filepath: StringProperty(
        name='File Path',
        description='File path used for exporting the PSK file',
        maxlen=1024,
        default='')

    def invoke(self, context, event):
        try:
            input_objects = PskBuilder.get_input_objects(context)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}

        pg = context.scene.psk_export

        # Populate bone groups list.
        populate_bone_group_list(input_objects.armature_object, pg.bone_group_list)

        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        pg = scene.psk_export

        # BONES
        box = layout.box()
        box.label(text='Bones', icon='BONE_DATA')
        bone_filter_mode_items = pg.bl_rna.properties['bone_filter_mode'].enum_items_static
        row = box.row(align=True)
        for item in bone_filter_mode_items:
            identifier = item.identifier
            item_layout = row.row(align=True)
            item_layout.prop_enum(pg, 'bone_filter_mode', item.identifier)
            item_layout.enabled = is_bone_filter_mode_item_available(context, identifier)

        if pg.bone_filter_mode == 'BONE_GROUPS':
            row = box.row()
            rows = max(3, min(len(pg.bone_group_list), 10))
            row.template_list('PSX_UL_BoneGroupList', '', pg, 'bone_group_list', pg, 'bone_group_list_index', rows=rows)

    def execute(self, context):
        pg = context.scene.psk_export
        builder = PskBuilder()
        options = PskBuilderOptions()
        options.bone_filter_mode = pg.bone_filter_mode
        options.bone_group_indices = [x.index for x in pg.bone_group_list if x.is_selected]
        try:
            psk = builder.build(context, options)
            exporter = PskExporter(psk)
            exporter.export(self.filepath)
        except RuntimeError as e:
            self.report({'ERROR_INVALID_CONTEXT'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


class PskExportPropertyGroup(PropertyGroup):
    bone_filter_mode: EnumProperty(
        name='Bone Filter',
        description='',
        items=(
            ('ALL', 'All', 'All bones will be exported.'),
            ('BONE_GROUPS', 'Bone Groups', 'Only bones belonging to the selected bone groups and their ancestors will be exported.')
        )
    )
    bone_group_list: CollectionProperty(type=BoneGroupListItem)
    bone_group_list_index: IntProperty(default=0)


classes = (
    PskExportOperator,
    PskExportPropertyGroup
)