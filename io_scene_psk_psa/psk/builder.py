import typing
from collections import Counter
from typing import Dict, Generator, Set, Iterable, Optional, cast

import bmesh
import bpy
import numpy as np
from bpy.types import Material, Collection, Context, Object, Armature, Bone

from .data import *
from .properties import triangle_type_and_bit_flags_to_poly_flags
from ..shared.dfs import dfs_collection_objects, dfs_view_layer_objects, DfsObject
from ..shared.helpers import get_coordinate_system_transform, convert_string_to_cp1252_bytes, \
    get_export_bone_names, convert_blender_bones_to_psx_bones


class PskInputObjects(object):
    def __init__(self):
        self.mesh_objects: List[DfsObject] = []
        self.armature_objects: Set[Object] = set()


class PskBuildOptions(object):
    def __init__(self):
        self.bone_filter_mode = 'ALL'
        self.bone_collection_indices: List[Tuple[str, int]] = []
        self.object_eval_state = 'EVALUATED'
        self.materials: List[Material] = []
        self.scale = 1.0
        self.export_space = 'WORLD'
        self.forward_axis = 'X'
        self.up_axis = 'Z'
        self.root_bone_name = 'ROOT'


def get_mesh_objects_for_collection(collection: Collection) -> Iterable[DfsObject]:
    return filter(lambda x: x.obj.type == 'MESH', dfs_collection_objects(collection))


def get_mesh_objects_for_context(context: Context) -> Iterable[DfsObject]:
    for dfs_object in dfs_view_layer_objects(context.view_layer):
        if dfs_object.obj.type == 'MESH' and dfs_object.is_selected:
            yield dfs_object


def get_armature_for_mesh_object(mesh_object: Object) -> Optional[Object]:
    for modifier in mesh_object.modifiers:
        if modifier.type == 'ARMATURE':
            return modifier.object
    return None


def get_armatures_for_mesh_objects(mesh_objects: Iterable[Object]) -> Generator[Object, None, None]:
    # Ensure that there are either no armature modifiers (static mesh) or that there is exactly one armature modifier
    # object shared between all meshes.
    armature_objects = set()
    for mesh_object in mesh_objects:
        modifiers = [x for x in mesh_object.modifiers if x.type == 'ARMATURE']
        if len(modifiers) == 0:
            continue
        if modifiers[0].object in armature_objects:
            continue
        yield modifiers[0].object


def _get_psk_input_objects(mesh_objects: Iterable[DfsObject]) -> PskInputObjects:
    mesh_objects = list(mesh_objects)
    if len(mesh_objects) == 0:
        raise RuntimeError('At least one mesh must be selected')

    input_objects = PskInputObjects()
    input_objects.mesh_objects = mesh_objects
    input_objects.armature_objects |= set(get_armatures_for_mesh_objects(map(lambda x: x.obj, mesh_objects)))

    return input_objects


def get_psk_input_objects_for_context(context: Context) -> PskInputObjects:
    mesh_objects = list(get_mesh_objects_for_context(context))
    return _get_psk_input_objects(mesh_objects)


def get_psk_input_objects_for_collection(collection: Collection, should_exclude_hidden_meshes: bool = True) -> PskInputObjects:
    mesh_objects = get_mesh_objects_for_collection(collection)
    if should_exclude_hidden_meshes:
        mesh_objects = filter(lambda x: x.is_visible, mesh_objects)
    return _get_psk_input_objects(mesh_objects)


class PskBuildResult(object):
    def __init__(self):
        self.psk = None
        self.warnings: List[str] = []


def _get_mesh_export_space_matrix(armature_objects: Iterable[Object], export_space: str) -> Matrix:
    if not armature_objects:
        return Matrix.Identity(4)

    def get_object_space_space_matrix(obj: Object) -> Matrix:
        translation, rotation, _ = obj.matrix_world.decompose()
        # We neutralize the scale here because the scale is already applied to the mesh objects implicitly.
        return Matrix.Translation(translation) @ rotation.to_matrix().to_4x4()


    match export_space:
        case 'WORLD':
            return Matrix.Identity(4)
        case 'ARMATURE':
            return get_object_space_space_matrix(armature_objects[0]).inverted()
        case 'ROOT':
            # TODO: multiply this by the root bone's local matrix
            armature_object = armature_objects[0]
            armature_data = cast(armature_object.data, Armature)
            armature_space_matrix = get_object_space_space_matrix(armature_object) @ armature_data.bones[0].matrix_local
            return armature_space_matrix.inverted()
        case _:
            assert False, f'Invalid export space: {export_space}'


def _get_material_name_indices(obj: Object, material_names: List[str]) -> Iterable[int]:
    '''
    Returns the index of the material in the list of material names.
    If the material is not found, the index 0 is returned.
    '''
    for material_slot in obj.material_slots:
        if material_slot.material is None:
            yield 0
        else:
            try:
                yield material_names.index(material_slot.material.name)
            except ValueError:
                yield 0


def build_psk(context, input_objects: PskInputObjects, options: PskBuildOptions) -> PskBuildResult:
    armature_objects = list(input_objects.armature_objects)

    result = PskBuildResult()
    psk = Psk()
    bones: List[Bone] = []

    if options.export_space != 'WORLD' and len(armature_objects) > 1:
        raise RuntimeError('When exporting multiple armatures, the Export Space must be World')

    coordinate_system_matrix = get_coordinate_system_transform(options.forward_axis, options.up_axis)
    coordinate_system_default_rotation = coordinate_system_matrix.to_quaternion()

    scale_matrix = Matrix.Scale(options.scale, 4)

    total_bone_count = sum(len(armature_object.data.bones) for armature_object in armature_objects)

    # Store the index of the root bone for each armature object.
    # We will need this later to correctly assign vertex weights.
    armature_object_root_bone_indices = dict()

    # Store the bone names to be exported for each armature object.
    armature_object_bone_names: Dict[Object, List[str]] = dict()
    for armature_object in  armature_objects:
        bone_collection_indices = [x[1] for x in options.bone_collection_indices if x[0] == armature_object.name]
        bone_names = get_export_bone_names(armature_object, options.bone_filter_mode, bone_collection_indices)
        armature_object_bone_names[armature_object] = bone_names

    if len(armature_objects) == 0 or total_bone_count == 0:
        # If the mesh has no armature object or no bones, simply assign it a dummy bone at the root to satisfy the
        # requirement that a PSK file must have at least one bone.
        psk_bone = Psk.Bone()
        psk_bone.name = convert_string_to_cp1252_bytes(options.root_bone_name)
        psk_bone.flags = 0
        psk_bone.children_count = 0
        psk_bone.parent_index = 0
        psk_bone.location = Vector3.zero()
        psk_bone.rotation = Quaternion.from_bpy_quaternion(coordinate_system_default_rotation)
        psk.bones.append(psk_bone)

        armature_object_root_bone_indices[None] = 0
    else:
        # If we have multiple armature objects, create a root bone at the world origin.
        if len(armature_objects) > 1:
            psk_bone = Psk.Bone()
            psk_bone.name = convert_string_to_cp1252_bytes(options.root_bone_name)
            psk_bone.flags = 0
            psk_bone.children_count = total_bone_count
            psk_bone.parent_index = 0
            psk_bone.location = Vector3.zero()
            psk_bone.rotation = Quaternion.from_bpy_quaternion(coordinate_system_default_rotation)
            psk.bones.append(psk_bone)

            armature_object_root_bone_indices[None] = 0

        root_bone = psk.bones[0] if len(psk.bones) > 0 else None

        for armature_object in armature_objects:
            bone_names = armature_object_bone_names[armature_object]
            armature_data = typing.cast(Armature, armature_object.data)
            bones = [armature_data.bones[bone_name] for bone_name in bone_names]

            psk_bones = convert_blender_bones_to_psx_bones(
                bones=bones,
                bone_class=Psk.Bone,
                export_space=options.export_space,
                armature_object_matrix_world=armature_object.matrix_world,
                scale=options.scale,
                forward_axis=options.forward_axis,
                up_axis=options.up_axis,
                root_bone=root_bone,
            )

            # If we are appending these bones to an existing list of bones, we need to adjust the parent indices.
            if len(psk.bones) > 0:
                parent_index_offset = len(psk.bones)
                for bone in psk_bones[1:]:
                    bone.parent_index += parent_index_offset

            armature_object_root_bone_indices[armature_object] = len(psk.bones)

            psk.bones.extend(psk_bones)

    # Check if there are bone name conflicts between armatures.
    bone_name_counts = Counter(x.name.decode('windows-1252').upper() for x in psk.bones)

    for bone_name, count in bone_name_counts.items():
        if count > 1:
            raise RuntimeError(f'Found {count} bones with the name "{bone_name}". Bone names must be unique when compared case-insensitively.')

    # Materials
    for material in options.materials:
        psk_material = Psk.Material()
        psk_material.name = convert_string_to_cp1252_bytes(material.name)
        psk_material.texture_index = len(psk.materials)
        psk_material.poly_flags = triangle_type_and_bit_flags_to_poly_flags(material.psk.mesh_triangle_type,
                                                                            material.psk.mesh_triangle_bit_flags)
        psk.materials.append(psk_material)

    # TODO: This wasn't left in a good state. We should detect if we need to add a "default" material.
    #  This can be done by checking if there is an empty material slot on any of the mesh objects, or if there are
    #  no material slots on any of the mesh objects.
    #  If so, it should be added to the end of the list of materials, and its index should mapped to a None value in the
    #  material indices list.
    if len(psk.materials) == 0:
        # Add a default material if no materials are present.
        psk_material = Psk.Material()
        psk_material.name = convert_string_to_cp1252_bytes('None')
        psk.materials.append(psk_material)

    context.window_manager.progress_begin(0, len(input_objects.mesh_objects))

    mesh_export_space_matrix = _get_mesh_export_space_matrix(armature_objects, options.export_space)
    vertex_transform_matrix = scale_matrix @ coordinate_system_matrix @ mesh_export_space_matrix

    original_armature_object_pose_positions = {armature_object: armature_object.data.pose_position for armature_object in armature_objects}

    # Temporarily force the armature into the rest position.
    # We will undo this later.
    for armature_object in armature_objects:
        armature_object.data.pose_position = 'REST'

    material_names = [m.name for m in options.materials]

    for object_index, input_mesh_object in enumerate(input_objects.mesh_objects):
        obj, instance_objects, matrix_world = input_mesh_object.obj, input_mesh_object.instance_objects, input_mesh_object.matrix_world

        armature_object = get_armature_for_mesh_object(obj)

        should_flip_normals = False

        # Material indices
        material_indices = list(_get_material_name_indices(obj, material_names))

        if len(material_indices) == 0:
            # Add a default material if no materials are present.
            material_indices = [0]

        # Store the reference to the evaluated object and data so that we can clean them up later.
        evaluated_mesh_object = None
        evaluated_mesh_data = None

        # Mesh data
        match options.object_eval_state:
            case 'ORIGINAL':
                mesh_object = obj
                mesh_data = obj.data
            case 'EVALUATED':
                # Create a copy of the mesh object after non-armature modifiers are applied.
                depsgraph = context.evaluated_depsgraph_get()
                bm = bmesh.new()

                try:
                    bm.from_object(obj, depsgraph)
                except ValueError as e:
                    del bm
                    raise RuntimeError(f'Object "{obj.name}" is not evaluated.\n'
                    'This is likely because the object is in a collection that has been excluded from the view layer.') from e

                evaluated_mesh_data = bpy.data.meshes.new('')
                mesh_data = evaluated_mesh_data
                bm.to_mesh(mesh_data)
                del bm
                evaluated_mesh_object = bpy.data.objects.new('', mesh_data)
                mesh_object =  evaluated_mesh_object
                mesh_object.matrix_world = matrix_world

                # Extract the scale from the matrix.
                _, _, scale = matrix_world.decompose()

                # Negative scaling in Blender results in inverted normals after the scale is applied. However, if the
                # scale is not applied, the normals will appear unaffected in the viewport. The evaluated mesh data used
                # in the export will have the scale applied, but this behavior is not obvious to the user.
                #
                # In order to have the exporter be as WYSIWYG as possible, we need to check for negative scaling and
                # invert the normals if necessary. If two axes have negative scaling and the third has positive scaling,
                # the normals will be correct. We can detect this by checking if the number of negative scaling axes is
                # odd. If it is, we need to invert the normals of the mesh by swapping the order of the vertices in each
                # face.
                should_flip_normals = sum(1 for x in scale if x < 0) % 2 == 1

                # Copy the vertex groups
                for vertex_group in obj.vertex_groups:
                    mesh_object.vertex_groups.new(name=vertex_group.name)
            case _:
                assert False, f'Invalid object evaluation state: {options.object_eval_state}'

        vertex_offset = len(psk.points)
        point_transform_matrix = vertex_transform_matrix @ mesh_object.matrix_world

        # Vertices
        for vertex in mesh_data.vertices:
            point = Vector3()
            v = point_transform_matrix @ vertex.co
            point.x = v.x
            point.y = v.y
            point.z = v.z
            psk.points.append(point)

        uv_layer = mesh_data.uv_layers.active.data

        # Wedges
        mesh_data.calc_loop_triangles()

        # Build a list of non-unique wedges.
        wedges = []
        for loop_index, loop in enumerate(mesh_data.loops):
            wedges.append(Psk.Wedge(
                point_index=loop.vertex_index + vertex_offset,
                u=uv_layer[loop_index].uv[0],
                v=1.0 - uv_layer[loop_index].uv[1]
            ))

        # Assign material indices to the wedges.
        for triangle in mesh_data.loop_triangles:
            for loop_index in triangle.loops:
                wedges[loop_index].material_index = material_indices[triangle.material_index]

        # Populate the list of wedges with unique wedges & build a look-up table of loop indices to wedge indices.
        wedge_indices = dict()
        loop_wedge_indices = np.full(len(mesh_data.loops), -1)
        for loop_index, wedge in enumerate(wedges):
            wedge_hash = hash(wedge)
            if wedge_hash in wedge_indices:
                loop_wedge_indices[loop_index] = wedge_indices[wedge_hash]
            else:
                wedge_index = len(psk.wedges)
                wedge_indices[wedge_hash] = wedge_index
                psk.wedges.append(wedge)
                loop_wedge_indices[loop_index] = wedge_index

        # Faces
        poly_groups, groups = mesh_data.calc_smooth_groups(use_bitflags=True)
        psk_face_start_index = len(psk.faces)
        for f in mesh_data.loop_triangles:
            face = Psk.Face()
            face.material_index = material_indices[f.material_index]
            face.wedge_indices[0] = loop_wedge_indices[f.loops[2]]
            face.wedge_indices[1] = loop_wedge_indices[f.loops[1]]
            face.wedge_indices[2] = loop_wedge_indices[f.loops[0]]
            face.smoothing_groups = poly_groups[f.polygon_index]
            psk.faces.append(face)

        if should_flip_normals:
            # Invert the normals of the faces.
            for face in psk.faces[psk_face_start_index:]:
                face.wedge_indices[0], face.wedge_indices[2] = face.wedge_indices[2], face.wedge_indices[0]

        # Weights
        if armature_object is not None:
            armature_data = typing.cast(Armature, armature_object.data)
            bone_index_offset = armature_object_root_bone_indices[armature_object]
            # Because the vertex groups may contain entries for which there is no matching bone in the armature,
            # we must filter them out and not export any weights for these vertex groups.

            bone_names = armature_object_bone_names[armature_object]
            vertex_group_names = [x.name for x in mesh_object.vertex_groups]
            vertex_group_bone_indices: Dict[int, int] = dict()
            for vertex_group_index, vertex_group_name in enumerate(vertex_group_names):
                try:
                    vertex_group_bone_indices[vertex_group_index] = bone_names.index(vertex_group_name) + bone_index_offset
                except ValueError:
                    # The vertex group does not have a matching bone in the list of bones to be exported.
                    # Check to see if there is an associated bone for this vertex group that exists in the armature.
                    # If there is, we can traverse the ancestors of that bone to find an alternate bone to use for
                    # weighting the vertices belonging to this vertex group.
                    if vertex_group_name in armature_data.bones:
                        bone = armature_data.bones[vertex_group_name]
                        while bone is not None:
                            try:
                                vertex_group_bone_indices[vertex_group_index] = bone_names.index(bone.name) + bone_index_offset
                                break
                            except ValueError:
                                bone = bone.parent

            # Keep track of which vertices have been assigned weights.
            # The ones that have not been assigned weights will be assigned to the root bone.
            # Without this, some older versions of UnrealEd may have corrupted meshes.
            vertices_assigned_weights = np.full(len(mesh_data.vertices), False)

            for vertex_group_index, vertex_group in enumerate(mesh_object.vertex_groups):
                if vertex_group_index not in vertex_group_bone_indices:
                    # Vertex group has no associated bone, skip it.
                    continue
                bone_index = vertex_group_bone_indices[vertex_group_index]
                for vertex_index in range(len(mesh_data.vertices)):
                    try:
                        weight = vertex_group.weight(vertex_index)
                    except RuntimeError:
                        continue
                    if weight == 0.0:
                        continue
                    w = Psk.Weight()
                    w.bone_index = bone_index
                    w.point_index = vertex_offset + vertex_index
                    w.weight = weight
                    psk.weights.append(w)
                    vertices_assigned_weights[vertex_index] = True

            # Assign vertices that have not been assigned weights to the root bone of the armature.
            fallback_weight_bone_index = armature_object_root_bone_indices[armature_object]
            for vertex_index, assigned in enumerate(vertices_assigned_weights):
                if not assigned:
                    w = Psk.Weight()
                    w.bone_index = fallback_weight_bone_index
                    w.point_index = vertex_offset + vertex_index
                    w.weight = 1.0
                    psk.weights.append(w)

        if evaluated_mesh_object is not None:
            bpy.data.objects.remove(mesh_object)
            del mesh_object

        if evaluated_mesh_data is not None:
            bpy.data.meshes.remove(mesh_data)
            del mesh_data

        context.window_manager.progress_update(object_index)

    # Restore the original pose position of the armature objects.
    for armature_object, pose_position in original_armature_object_pose_positions.items():
        armature_object.data.pose_position = pose_position

    context.window_manager.progress_end()

    result.psk = psk

    return result
