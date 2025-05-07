from ctypes import Structure, c_uint32, c_float, c_int32, c_uint8, c_int8, c_int16, c_char, c_uint16
from typing import List

from ..shared.data import Vector3, Quaternion, Color, Vector2, PsxBone


class Psk(object):
    class Wedge(object):
        def __init__(self, point_index: int, u: float, v: float, material_index: int = 0):
            self.point_index: int = point_index
            self.u: float = u
            self.v: float = v
            self.material_index = material_index

        def __hash__(self):
            return hash(f'{self.point_index}-{self.u}-{self.v}-{self.material_index}')

    class Wedge16(Structure):
        _fields_ = [
            ('point_index', c_uint32),
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

    class Face32(Structure):
        _pack_ = 1
        _fields_ = [
            ('wedge_indices', c_uint32 * 3),
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

    class MorphInfo(Structure):
        _fields_ = [
            ('name', c_char * 64),
            ('vertex_count', c_int32)
        ]

    class MorphData(Structure):
        _fields_ = [
            ('position_delta', Vector3),
            ('tangent_z_delta', Vector3),
            ('point_index', c_int32)
        ]

    @property
    def has_extra_uvs(self):
        return len(self.extra_uvs) > 0

    @property
    def has_vertex_colors(self):
        return len(self.vertex_colors) > 0

    @property
    def has_vertex_normals(self):
        return len(self.vertex_normals) > 0

    @property
    def has_material_references(self):
        return len(self.material_references) > 0

    @property
    def has_morph_data(self):
        return len(self.morph_infos) > 0
    
    def sort_and_normalize_weights(self):
        self.weights.sort(key=lambda x: x.point_index)

        weight_index = 0
        weight_total = len(self.weights)

        while weight_index < weight_total:
            point_index = self.weights[weight_index].point_index
            weight_sum = self.weights[weight_index].weight
            point_weight_total = 1

            # Calculate the sum of weights for the current point_index.
            for i in range(weight_index + 1, weight_total):
                if self.weights[i].point_index != point_index:
                    break
                weight_sum += self.weights[i].weight
                point_weight_total += 1

            # Normalize the weights for the current point_index.
            for i in range(weight_index, weight_index + point_weight_total):
                self.weights[i].weight /= weight_sum

            # Move to the next group of weights.
            weight_index += point_weight_total
    
    def __init__(self):
        self.points: List[Vector3] = []
        self.wedges: List[Psk.Wedge] = []
        self.faces: List[Psk.Face] = []
        self.materials: List[Psk.Material] = []
        self.weights: List[Psk.Weight] = []
        self.bones: List[PsxBone] = []
        self.extra_uvs: List[Vector2] = []
        self.vertex_colors: List[Color] = []
        self.vertex_normals: List[Vector3] = []
        self.morph_infos: List[Psk.MorphInfo] = []
        self.morph_data: List[Psk.MorphData] = []
        self.material_references: List[str] = []
