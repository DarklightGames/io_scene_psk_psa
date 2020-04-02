from typing import List
from ..data import *


class Psa(object):

    class Bone(Structure):
        _fields_ = [
            ('name', c_char * 64),
            ('flags', c_int32),
            ('children_count', c_int32),
            ('parent_index', c_int32),
            ('rotation', Quaternion),
            ('location', Vector3),
            ('padding', c_char * 16)
        ]

    class Sequence(Structure):
        _fields_ = [
            ('name', c_char * 64),
            ('group', c_char * 64),
            ('bone_count', c_int32),
            ('root_include', c_int32),
            ('compression_style', c_int32),
            ('key_quotum', c_int32),  # what the fuck is a quotum
            ('key_reduction', c_float),
            ('track_time', c_float),
            ('fps', c_float),
            ('start_bone', c_int32),
            ('frame_start_index', c_int32),
            ('frame_count', c_int32)
        ]

    class Key(Structure):
        _fields_ = [
            ('location', Vector3),
            ('rotation', Quaternion),
            ('time', c_float)
        ]

    def __init__(self):
        self.bones: List[Psa.Bone] = []
        self.sequences: List[Psa.Sequence] = []
        self.keys: List[Psa.Key] = []
