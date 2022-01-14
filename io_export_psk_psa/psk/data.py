from typing import List
from ..data import *


class Psk(object):

    class Wedge(object):
        def __init__(self):
            self.point_index: int = 0
            self.u: float = 0.0
            self.v: float = 0.0
            self.material_index: int = 0

        def __hash__(self):
            return hash(f'{self.point_index}-{self.u}-{self.v}-{self.material_index}')

    class Wedge16(Structure):
        _fields_ = [
            ('point_index', c_uint16),
            ('padding1', c_int16),
            ('u', c_float),
            ('v', c_float),
            ('material_index', c_uint8),
            ('reserved', c_int8),
            ('padding2', c_int16)
        ]

    class Wedge32(Structure):
        _fields_ = [
            ('point_index', c_uint32),
            ('u', c_float),
            ('v', c_float),
            ('material_index', c_uint32)
        ]

    class Face(Structure):
        _fields_ = [
            ('wedge_indices', c_uint16 * 3),
            ('material_index', c_uint8),
            ('aux_material_index', c_uint8),
            ('smoothing_groups', c_int32)
        ]

    class Material(Structure):
        _fields_ = [
            ('name', c_char * 64),
            ('texture_index', c_int32),
            ('poly_flags', c_int32),
            ('aux_material', c_int32),
            ('aux_flags', c_int32),
            ('lod_bias', c_int32),
            ('lod_style', c_int32)
        ]

    class Bone(Structure):
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

    class Weight(Structure):
        _fields_ = [
            ('weight', c_float),
            ('point_index', c_int32),
            ('bone_index', c_int32),
        ]

    def __init__(self):
        self.points: List[Vector3] = []
        self.wedges: List[Psk.Wedge] = []
        self.faces: List[Psk.Face] = []
        self.materials: List[Psk.Material] = []
        self.weights: List[Psk.Weight] = []
        self.bones: List[Psk.Bone] = []
