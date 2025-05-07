import bmesh
import bpy
import numpy as np
from bpy.types import Armature, Collection, Context, Depsgraph, Object
from mathutils import Matrix
from typing import Dict, Generator, Iterable, List, Optional, Set, Tuple, cast as typing_cast
from .data import Psk
from .properties import triangle_type_and_bit_flags_to_poly_flags
from ..shared.data import Vector3
from ..shared.dfs import DfsObject, dfs_collection_objects, dfs_view_layer_objects
from ..shared.helpers import (
    convert_string_to_cp1252_bytes,
    create_psx_bones,
    get_coordinate_system_transform,
)


class PskInputObjects(object):
    def __init__(self):
        self.mesh_dfs_objects: List[DfsObject] = []
        self.armature_objects: Set[Object] = set()


class PskBuildOptions(object):
    def __init__(self):
        self.bone_filter_mode = 'ALL'
        self.bone_collection_indices: List[Tuple[str, int]] = []
        self.object_eval_state = 'EVALUATED'
        self.material_order_mode = 'AUTOMATIC'
        self.material_name_list: List[str] = []
        self.scale = 1.0
        self.export_space = 'WORLD'
        self.forward_axis = 'X'
        self.up_axis = 'Z'
        self.root_bone_name = 'ROOT'


def get_materials_for_mesh_objects(depsgraph: Depsgraph, mesh_objects: Iterable[Object]):
    yielded_materials = set()
    for mesh_object in mesh_objects:
        evaluated_mesh_object = mesh_object.evaluated_get(depsgraph)
        for i, material_slot in enumerate(evaluated_mesh_object.material_slots):
            material = material_slot.material
            if material is None:
                raise RuntimeError('Material slot cannot be empty (index ' + str(i) + ')')
            if material not in yielded_materials:
                yielded_materials.add(material)
                yield material


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


def _get_psk_input_objects(mesh_dfs_objects: Iterable[DfsObject]) -> PskInputObjects:
    mesh_dfs_objects = list(mesh_dfs_objects)
    if len(mesh_dfs_objects) == 0:
        raise RuntimeError('At least one mesh must be selected')

    input_objects = PskInputObjects()
    input_objects.mesh_dfs_objects = mesh_dfs_objects
    input_objects.armature_objects |= set(get_armatures_for_mesh_objects(map(lambda x: x.obj, mesh_dfs_objects)))

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


def _get_mesh_export_space_matrix(armature_object: Optional[Object], export_space: str) -> Matrix:
    if armature_object is None:
        return Matrix.Identity(4)

    def get_object_space_matrix(obj: Object) -> Matrix:
        translation, rotation, _ = obj.matrix_world.decompose()
        # We neutralize the scale here because the scale is already applied to the mesh objects implicitly.
        return Matrix.Translation(translation) @ rotation.to_matrix().to_4x4()

    match export_space:
        case 'WORLD':
            return Matrix.Identity(4)
        case 'ARMATURE':
            return get_object_space_matrix(armature_object).inverted()
        case 'ROOT':
            armature_data = typing_cast(Armature, armature_object.data)
            armature_space_matrix = get_object_space_matrix(armature_object) @ armature_data.bones[0].matrix_local
            return armature_space_matrix.inverted()
        case _:
            assert False, f'Invalid export space: {export_space}'


def _get_material_name_indices(obj: Object, material_names: List[str]) -> Iterable[int]:
    """
    Returns the index of the material in the list of material names.
    If the material is not found, the index 0 is returned.
    """
    for material_slot in obj.material_slots:
        if material_slot.material is None:
            yield 0
        else:
            try:
                yield material_names.index(material_slot.material.name)
            except ValueError:
                yield 0


def build_psk(context: Context, input_objects: PskInputObjects, options: PskBuildOptions) -> PskBuildResult:
    armature_objects = list(input_objects.armature_objects)

    result = PskBuildResult()
    psk = Psk()

    psx_bone_create_result = create_psx_bones(
        armature_objects=armature_objects,
        export_space=options.export_space,
        forward_axis=options.forward_axis,
        up_axis=options.up_axis,
        scale=options.scale,
        root_bone_name=options.root_bone_name,
        bone_filter_mode=options.bone_filter_mode,
        bone_collection_indices=options.bone_collection_indices
    )

    psk.bones = [psx_bone for psx_bone, _ in psx_bone_create_result.bones]

    # Materials
    match options.material_order_mode:
        case 'AUTOMATIC':
            mesh_objects = [dfs_object.obj for dfs_object in input_objects.mesh_dfs_objects]
            materials = list(get_materials_for_mesh_objects(context.evaluated_depsgraph_get(), mesh_objects))
        case 'MANUAL':
            # The material name list may contain materials that are not on the mesh objects.
            # Therefore, we can take the material_name_list as gospel and simply use it as a lookup table.
            # If a look-up fails, replace it with an empty material.
            materials = [bpy.data.materials.get(x.material_name, None) for x in options.material_name_list]
        case _:
            assert False, f'Invalid material order mode: {options.material_order_mode}'

    for material in materials:
        psk_material = Psk.Material()
        psk_material.name = convert_string_to_cp1252_bytes(material.name if material else 'None')
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

    context.window_manager.progress_begin(0, len(input_objects.mesh_dfs_objects))

    coordinate_system_matrix = get_coordinate_system_transform(options.forward_axis, options.up_axis)

    # Calculate the export spaces for the armature objects.
    # This is used later to transform the mesh object geometry into the export space.
    armature_mesh_export_space_matrices: Dict[Optional[Object], Matrix] = {None: Matrix.Identity(4)}
    for armature_object in armature_objects:
        armature_mesh_export_space_matrices[armature_object] = _get_mesh_export_space_matrix(armature_object, options.export_space)

    scale_matrix = Matrix.Scale(options.scale, 4)

    original_armature_object_pose_positions = {a: a.data.pose_position for a in armature_objects}

    # Temporarily force the armature into the rest position.
    # We will undo this later.
    for armature_object in armature_objects:
        armature_object.data.pose_position = 'REST'

    material_names = [m.name for m in materials]

    for object_index, input_mesh_object in enumerate(input_objects.mesh_dfs_objects):
        obj, matrix_world = input_mesh_object.obj, input_mesh_object.matrix_world

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
                if not should_flip_normals:
                    should_flip_normals = sum(1 for x in scale if x < 0) % 2 == 1

                # Copy the vertex groups
                for vertex_group in obj.vertex_groups:
                    mesh_object.vertex_groups.new(name=vertex_group.name)
            case _:
                assert False, f'Invalid object evaluation state: {options.object_eval_state}'

        mesh_export_space_matrix = armature_mesh_export_space_matrices[armature_object]
        vertex_transform_matrix = scale_matrix @ coordinate_system_matrix @ mesh_export_space_matrix
        point_transform_matrix = vertex_transform_matrix @ mesh_object.matrix_world

        # Vertices
        vertex_offset = len(psk.points)
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
            armature_data = typing_cast(Armature, armature_object.data)
            bone_index_offset = psx_bone_create_result.armature_object_root_bone_indices[armature_object]
            # Because the vertex groups may contain entries for which there is no matching bone in the armature,
            # we must filter them out and not export any weights for these vertex groups.

            bone_names = psx_bone_create_result.armature_object_bone_names[armature_object]
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
            fallback_weight_bone_index = psx_bone_create_result.armature_object_root_bone_indices[armature_object]
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

    # https://github.com/DarklightGames/io_scene_psk_psa/issues/129.
    psk.sort_and_normalize_weights()

    result.psk = psk

    return result
