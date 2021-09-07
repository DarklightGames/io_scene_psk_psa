import bpy
import bmesh
import mathutils
from .data import Psa


class PsaImporter(object):
    def __init__(self):
        pass

    def import_psa(self, psa: Psa, context):
        print('importing yay')
        print(psa.sequences)
        for sequence in psa.sequences:
            print(sequence.name, sequence.frame_start_index, sequence.frame_count)
