from ctypes import Structure, c_char, c_int32, c_float, c_ubyte
from typing import Tuple


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
