import bpy
import bmesh
from .psk import Psk, Vector3


class PskBuilder(object):
    def __init__(self):
        pass

    def build(self, context) -> Psk:
        object = context.view_layer.objects.active
        if object.type != 'MESH':
            raise RuntimeError('Selected object must be a Mesh')

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

        # vertices
        for vertex in mesh.vertices:
            psk.points.append(Vector3(*vertex.co))

        # TODO: wedges (a "wedge" is actually a UV'd vertex, basically)
        # for wedge in mesh.wedges:
        #     pass

        # materials
        for i, m in enumerate(object.data.materials):
            material = Psk.Material()
            material.name = m.name
            material.texture_index = i
            psk.materials.append(material)

        # TODO: should we make the wedges/faces at the same time??
        f = Psk.Face()
        # f.wedge_index_1 = 0

        # TODO: weights

        return psk
