from typing import List, Dict
from ..data import *

"""
Note that keys are not stored within the Psa object.
Use the PsaReader::get_sequence_keys to get a the keys for a sequence.
"""


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
            ('key_quotum', c_int32),
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

        def __repr__(self) -> str:
            return repr((self.location, self.rotation, self.time))

    def __init__(self):
        self.bones: List[Psa.Bone] = []
        self.sequences: Dict[Psa.Sequence] = {}
