import bpy
import bmesh
import mathutils
from .psk import Psk, Vector3


class PskBuilder(object):
    def __init__(self):
        pass

    def build(self, context) -> Psk:
        object = context.view_layer.objects.active

        if object.type != 'MESH':
            raise RuntimeError('selected object must be a mesh')

        if len(object.data.materials) == 0:
            raise RuntimeError('the mesh must have at least one material')

        # ensure that there is exactly one armature modifier
        modifiers = [x for x in object.modifiers if x.type == 'ARMATURE']

        if len(modifiers) != 1:
            raise RuntimeError('the mesh must have one armature modifier')

        armature_modifier = modifiers[0]
        armature_object = armature_modifier.object

        if armature_object is None:
            raise RuntimeError('the armature modifier has no linked object')

        # TODO: probably requires at least one bone? not sure
        mesh_data = object.data

        # TODO: if there is an edge-split modifier, we need to apply it.

        # TODO: duplicate all the data
        mesh = bpy.data.meshes.new('export')

        # copy the contents of the mesh
        bm = bmesh.new()
        bm.from_mesh(mesh_data)
        # triangulate everything
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        del bm

        psk = Psk()

        # VERTICES
        for vertex in object.data.vertices:
            point = Vector3()
            point.x = vertex.co.x
            point.y = vertex.co.y
            point.z = vertex.co.z
            psk.points.append(point)

        # WEDGES
        uv_layer = object.data.uv_layers.active.data
        if len(object.data.loops) <= 65536:
            wedge_type = Psk.Wedge16
        else:
            wedge_type = Psk.Wedge32
        psk.wedges = [wedge_type() for _ in range(len(object.data.loops))]

        for loop_index, loop in enumerate(object.data.loops):
            wedge = psk.wedges[loop_index]
            wedge.material_index = 0
            wedge.point_index = loop.vertex_index
            wedge.u, wedge.v = uv_layer[loop_index].uv
            psk.wedges.append(wedge)

        # MATERIALS
        for i, m in enumerate(object.data.materials):
            material = Psk.Material()
            material.name = bytes(m.name, encoding='utf-8')
            material.texture_index = i
            psk.materials.append(material)

        # FACES
        # TODO: this is making the assumption that the mesh is triangulated
        object.data.calc_loop_triangles()
        poly_groups, groups = object.data.calc_smooth_groups(use_bitflags=True)
        for f in object.data.loop_triangles:
            face = Psk.Face()
            face.material_index = f.material_index
            face.wedge_index_1 = f.loops[2]
            face.wedge_index_2 = f.loops[1]
            face.wedge_index_3 = f.loops[0]
            face.smoothing_groups = poly_groups[f.polygon_index]
            psk.faces.append(face)
            # update the material index of the wedges
            for i in range(3):
                psk.wedges[f.loops[i]].material_index = f.material_index

        # BONES
        bone_list = list(armature_object.data.bones)
        for b in armature_object.data.bones:
            bone = psk.Bone()
            bone.name = bytes(b.name, encoding='utf-8')
            bone.children_count = len(b.children)
            bone.flags = 0  # look up what this is
            bone.length = 10.0  # TODO: not sure what this is
            try:
                bone.parent_index = bone_list.index(b.parent)
            except ValueError:
                # this should be -1?
                bone.parent_index = 0
            bone.position.x = b.head_local.x
            bone.position.y = b.head_local.y
            bone.position.z = b.head_local.z
            print(bone.name)
            print(bone.position.x)
            print(bone.position.y)
            print(bone.position.z)
            print('----')
            rotation = b.matrix_local.to_quaternion()
            bone.rotation.x = rotation.x
            bone.rotation.y = rotation.y
            bone.rotation.z = rotation.z
            bone.rotation.w = rotation.w
            # TODO: not sure what "size" is supposed to be exactly
            bone.size.x = 1
            bone.size.y = 1
            bone.size.z = 1
            psk.bones.append(bone)

        # WEIGHTS
        # TODO: bone ~> vg might not be 1:1, provide a nice error message if this is the case
        armature = armature_object.data
        bone_names = [x.name for x in armature.bones]
        vertex_group_names = [x.name for x in object.vertex_groups]
        bone_indices = [bone_names.index(name) for name in vertex_group_names]
        for vertex_group_index, vertex_group in enumerate(object.vertex_groups):
            bone_index = bone_indices[vertex_group_index]
            for vertex_index in range(len(object.data.vertices)):
                weight = vertex_group.weight(vertex_index)
                if weight == 0.0:
                    continue
                w = Psk.Weight()
                w.bone_index = bone_index
                w.point_index = vertex_index
                w.weight = weight
                psk.weights.append(w)

        return psk
