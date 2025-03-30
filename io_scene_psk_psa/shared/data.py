from ctypes import *
from typing import Tuple

from bpy.props import EnumProperty
from mathutils import Quaternion as BpyQuaternion


class Color(Structure):
    _fields_ = [
        ('r', c_ubyte),
        ('g', c_ubyte),
        ('b', c_ubyte),
        ('a', c_ubyte),
    ]

    def __iter__(self):
        yield self.r
        yield self.g
        yield self.b
        yield self.a

    def __eq__(self, other):
        return all(map(lambda x: x[0] == x[1], zip(self, other)))

    def __repr__(self):
        return repr(tuple(self))

    def normalized(self) -> Tuple:
        return tuple(map(lambda x: x / 255.0, iter(self)))


class Vector2(Structure):
    _fields_ = [
        ('x', c_float),
        ('y', c_float),
    ]

    def __iter__(self):
        yield self.x
        yield self.y

    def __repr__(self):
        return repr(tuple(self))


class Vector3(Structure):
    _fields_ = [
        ('x', c_float),
        ('y', c_float),
        ('z', c_float),
    ]

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __repr__(self):
        return repr(tuple(self))

    @classmethod
    def zero(cls):
        return Vector3(0, 0, 0)


class Quaternion(Structure):
    _fields_ = [
        ('x', c_float),
        ('y', c_float),
        ('z', c_float),
        ('w', c_float),
    ]

    def __iter__(self):
        yield self.w
        yield self.x
        yield self.y
        yield self.z

    def __repr__(self):
        return repr(tuple(self))

    @classmethod
    def identity(cls):
        return Quaternion(0, 0, 0, 1)

    @classmethod
    def from_bpy_quaternion(cls, other: BpyQuaternion) -> BpyQuaternion:
        quaternion = Quaternion()
        quaternion.x = other.x
        quaternion.y = other.y
        quaternion.z = other.z
        quaternion.w = other.w
        return quaternion


class PsxBone(Structure):
    _fields_ = [
        ('name', c_char * 64),
        ('flags', c_int32),
        ('children_count', c_int32),
        ('parent_index', c_int32),
        ('rotation', Quaternion),
        ('location', Vector3),
        ('length', c_float),
        ('size', Vector3)
    ]


class Section(Structure):
    _fields_ = [
        ('name', c_char * 20),
        ('type_flags', c_int32),
        ('data_size', c_int32),
        ('data_count', c_int32)
    ]

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.type_flags = 1999801


bone_filter_mode_items = (
    ('ALL', 'All', 'All bones will be exported'),
    ('BONE_COLLECTIONS', 'Bone Collections', 'Only bones belonging to the selected bone collections and their ancestors will be exported')
)

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


def forward_axis_update(self, _context):
    if self.forward_axis == self.up_axis:
        # Automatically set the up axis to the next available axis
        self.up_axis = next((axis for axis in axis_identifiers if axis != self.forward_axis), 'Z')


def up_axis_update(self, _context):
    if self.up_axis == self.forward_axis:
        # Automatically set the forward axis to the next available axis
        self.forward_axis = next((axis for axis in axis_identifiers if axis != self.up_axis), 'X')


class ForwardUpAxisMixin:
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


export_space_items = [
    ('WORLD', 'World', 'Export in world space'),
    ('ARMATURE', 'Armature', 'Export the local space of the armature object'),
    ('ROOT', 'Root', 'Export in the space of the root bone')
]

class ExportSpaceMixin:
    export_space: EnumProperty(
        name='Export Space',
        items=export_space_items,
        default='WORLD'
    )
