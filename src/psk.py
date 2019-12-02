from typing import List

class Vector3(object):
    def __init__(self, x = 0, y = 0, z = 0):
        self.x = x
        self.y = y
        self.z = z

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z


class Quaternion(object):
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.w = 0.0

class Psk(object):

    class Wedge(object):
        def __init__(self):
            self.point_index = -1
            self.u = 0.0
            self.v = 0.0
            self.material_index = -1

    class Face(object):
        def __init__(self):
            self.wedge_index_1 = -1
            self.wedge_index_2 = -1
            self.wedge_index_3 = -1
            self.material_index = -1
            self.aux_material_index = -1
            self.smoothing_groups = -1

    class Material(object):
        def __init__(self):
            self.name = ''
            self.texture_index = -1
            self.poly_flags = 0
            self.aux_material_index = -1
            self.aux_flags = -1
            self.lod_bias = 0
            self.lod_style = 0

    class Bone(object):
        def __init__(self):
            self.name = ''
            self.flags = 0
            self.children_count = 0
            self.parent_index = -1
            self.rotation = Quaternion()
            self.position = Vector3()
            self.length = 0.0
            self.size = Vector3()

    class Weight(object):
        def __init__(self):
            self.weight = 0.0
            self.point_index = -1
            self.bone_index = -1


    def __init__(self):
        self.points = []
        self.wedges: List[Psk.Wedge] = []
        self.faces: List[Psk.Face] = []
        self.materials: List[Psk.Material] = []
        self.weights: List[Psk.Weight] = []
        self.bones: List[Psk.Bone] = []
