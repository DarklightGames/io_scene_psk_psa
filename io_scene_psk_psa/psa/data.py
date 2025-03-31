from collections import OrderedDict
from typing import List, OrderedDict as OrderedDictType

from ctypes import Structure, c_char, c_int32, c_float
from ..shared.data import PsxBone, Quaternion, Vector3


class Psa:
    """
    Note that keys are not stored within the Psa object.
    Use the `PsaReader.get_sequence_keys` to get the keys for a sequence.
    """

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

        @property
        def data(self):
            yield self.rotation.w
            yield self.rotation.x
            yield self.rotation.y
            yield self.rotation.z
            yield self.location.x
            yield self.location.y
            yield self.location.z

        def __repr__(self) -> str:
            return repr((self.location, self.rotation, self.time))

    def __init__(self):
        self.bones: List[PsxBone] = []
        self.sequences: OrderedDictType[str, Psa.Sequence] = OrderedDict()
        self.keys: List[Psa.Key] = []
