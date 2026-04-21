import bmesh
import bpy
import numpy as np
from bpy.types import Armature, Context, Object, Mesh
from mathutils import Matrix, Quaternion
from typing import Iterable, cast as typing_cast
from psk_psa_py.shared.data import PsxBone, Vector3
from psk_psa_py.psk.data import Psk
from .properties import triangle_type_and_bit_flags_to_poly_flags
from ..shared.helpers import (
    ObjectNode,
    ObjectTree,
    PskInputObjects,
    PsxBoneCollection,
    convert_bpy_quaternion_to_psx_quaternion,
    convert_string_to_cp1252_bytes,
    create_psx_bones,
    get_armature_for_mesh_object,
    get_coordinate_system_transform,
    get_materials_for_mesh_objects,
)


class PskBuildOptions(object):
    def __init__(self):
        self.bone_filter_mode = 'ALL'
        self.bone_collection_indices: list[PsxBoneCollection] = []
        self.object_eval_state = 'EVALUATED'
        self.material_order_mode = 'AUTOMATIC'
        self.material_name_list: list[str] = []
        self.scale = 1.0
        self.export_space = 'WORLD'
        self.forward_axis = 'X'
        self.up_axis = 'Z'


class PskBuildResult(object):
    def __init__(self, psk: Psk, warnings: list[str]):
        self.psk: Psk = psk
        self.warnings: list[str] = warnings


def _get_mesh_export_space_matrix(node: ObjectNode | None, export_space: str) -> Matrix:
    if node is None:
        return Matrix.Identity(4)

    armature_object = node.object
    root_armature_object = node.root.object

    def get_object_space_matrix(obj: Object) -> Matrix:
        translation, rotation, _ = obj.matrix_world.decompose()
        # We neutralize the scale here because the scale is already applied to the mesh objects implicitly.
        return Matrix.Translation(translation) @ rotation.to_matrix().to_4x4()

    armature_space_matrix = get_object_space_matrix(armature_object)
    root_armature_space_matrix = get_object_space_matrix(root_armature_object)
    relative_matrix = root_armature_space_matrix @ armature_space_matrix.inverted()

    match export_space:
        case 'WORLD':
            return Matrix.Identity(4)
        case 'ARMATURE':
            return (armature_space_matrix @ relative_matrix).inverted()
        case 'ROOT':
            root_armature_data = typing_cast(Armature, root_armature_object.data)
            if len(root_armature_data.bones) == 0:
                raise RuntimeError(f'Armature {root_armature_data.name} has no bones')
            return (armature_space_matrix @ relative_matrix @ root_armature_data.bones[0].matrix_local).inverted()
        case _:
            assert False, f'Invalid export space: {export_space}'


def _get_material_name_indices(obj: Object, material_names: list[str]) -> Iterable[int]:
    """
    Returns the index of the material in the list of material names.
    If the material is not found or the slot is empty, the index of 'None' is returned.
    """
    for material_slot in obj.material_slots:
        try:
            material_name = material_slot.material.name if material_slot.material is not None else 'None'
            yield material_names.index(material_name)
        except ValueError:
            yield 0


def _matrix_to_numpy(matrix: Matrix) -> np.ndarray:
    """Convert a 4x4 mathutils.Matrix to a (4, 4) float32 numpy array."""
    return np.array([matrix[i][j] for i in range(4) for j in range(4)], dtype=np.float32).reshape(4, 4)


def _transform_vertices_numpy(co_flat: np.ndarray, matrix_np: np.ndarray) -> np.ndarray:
    """
    Apply a 4x4 transform matrix to a flat (V*3,) array of vertex coordinates.
    Returns a (V, 3) float32 array of transformed positions.
    """
    V = len(co_flat) // 3
    ones = np.ones(V, dtype=np.float32)
    coords_h = np.column_stack([co_flat.reshape(V, 3), ones])   # (V, 4)
    transformed = coords_h @ matrix_np.T                         # (V, 4)
    return transformed[:, :3]                                    # (V, 3)


def _build_wedges_numpy(
    mesh_data: Mesh,
    vertex_offset: int,
    material_indices: list[int],
) -> tuple[list['Psk.Wedge'], np.ndarray]:
    """
    Build the list of unique PSK wedges and a per-loop wedge index mapping.

    Returns
    -------
    unique_wedges      : list[Psk.Wedge]  -- deduplicated wedges ready to extend psk.wedges
    loop_wedge_indices : np.ndarray (L,) int32  -- maps every loop to its wedge index
                         (indices are relative to the start of this mesh's wedge block)
    """
    L = len(mesh_data.loops)
    T = len(mesh_data.loop_triangles)

    loop_verts = np.empty(L, dtype=np.int32)
    mesh_data.loops.foreach_get("vertex_index", loop_verts)

    if mesh_data.uv_layers.active:
        uv_flat = np.empty(L * 2, dtype=np.float32)
        mesh_data.uv_layers.active.data.foreach_get("uv", uv_flat)
        uv_flat = uv_flat.reshape(L, 2)
        us = uv_flat[:, 0]
        vs = 1.0 - uv_flat[:, 1]
    else:
        us = np.zeros(L, dtype=np.float32)
        vs = np.zeros(L, dtype=np.float32)

    # Each loop belongs to exactly one triangle. We need a (L,) array of
    # resolved material indices. Build a loop -> triangle map via foreach_get.
    tri_loops_flat = np.empty(T * 3, dtype=np.int32)
    tri_mat_flat   = np.empty(T,     dtype=np.int32)
    mesh_data.loop_triangles.foreach_get("loops",          tri_loops_flat)
    mesh_data.loop_triangles.foreach_get("material_index", tri_mat_flat)

    # Map each triangle's raw material index through the slot remapping table.
    resolved_tri_mat = np.array(material_indices, dtype=np.int32)[tri_mat_flat]  # (T,)

    # Scatter: for each triangle corner, write the resolved mat index to that loop slot.
    loop_mat = np.empty(L, dtype=np.int32)
    loop_mat[tri_loops_flat] = np.repeat(resolved_tri_mat, 3)

    # Build (L, 4) key array for deduplication.
    # Key = (point_index_global, u_bits, v_bits, mat_index)
    # Float bits reinterpreted as uint32 to allow exact integer comparison.
    point_indices_global = loop_verts + vertex_offset

    u_bits = np.ascontiguousarray(us).view(np.uint32)
    v_bits = np.ascontiguousarray(vs).view(np.uint32)

    keys = np.stack(
        [point_indices_global.astype(np.uint32), u_bits, v_bits, loop_mat.astype(np.uint32)],
        axis=1,
    )  # (L, 4) uint32, C-contiguous

    void_view = keys.view(np.dtype((np.void, 16))).ravel()
    _, uniq_idx, inv_idx = np.unique(void_view, return_index=True, return_inverse=True)

    # inv_idx is the wedge index (relative to this mesh) for every loop.
    loop_wedge_indices = inv_idx.astype(np.int32)  # (L,)

    unique_keys = keys[uniq_idx]  # (W, 4)
    u_unique    = unique_keys[:, 1].view(np.float32)
    v_unique    = unique_keys[:, 2].view(np.float32)

    unique_wedges = []
    for i in range(len(unique_keys)):
        wedge = Psk.Wedge(
            point_index=int(unique_keys[i, 0]),
            u=float(u_unique[i]),
            v=float(v_unique[i]),
        )
        wedge.material_index = int(unique_keys[i, 3])
        unique_wedges.append(wedge)

    return unique_wedges, loop_wedge_indices


def _build_faces_numpy(
    mesh_data: Mesh,
    loop_wedge_indices: np.ndarray,
    wedge_index_offset: int,
    material_indices: list[int],
) -> list['Psk.Face']:
    """
    Build the list of PSK faces from loop_triangles using numpy bulk reads.
    """
    T = len(mesh_data.loop_triangles)

    tri_loops_flat   = np.empty(T * 3, dtype=np.int32)
    tri_mat_flat     = np.empty(T,     dtype=np.int32)
    tri_poly_indices = np.empty(T,     dtype=np.int32)

    mesh_data.loop_triangles.foreach_get("loops",          tri_loops_flat)
    mesh_data.loop_triangles.foreach_get("material_index", tri_mat_flat)
    mesh_data.loop_triangles.foreach_get("polygon_index",  tri_poly_indices)

    tri_loops = tri_loops_flat.reshape(T, 3)  # (T, 3)

    w_all = (loop_wedge_indices + wedge_index_offset).astype(np.int32)  # (L,)
    tri_wedges = w_all[tri_loops]  # (T, 3)

    resolved_mat = np.array(material_indices, dtype=np.int32)[tri_mat_flat]  # (T,)

    poly_groups, _groups = mesh_data.calc_smooth_groups(use_bitflags=True)
    poly_groups_np = np.array(poly_groups, dtype=np.uint32)
    tri_smooth = poly_groups_np[tri_poly_indices]  # (T,)

    faces = []
    for i in range(T):
        face = Psk.Face(
            wedge_indices=(int(tri_wedges[i, 2]), int(tri_wedges[i, 1]), int(tri_wedges[i, 0])),
            material_index=int(resolved_mat[i]),
            smoothing_groups=int(tri_smooth[i]),
        )
        faces.append(face)

    return faces


def _build_weights_numpy(
    mesh_data: Mesh,
    mesh_object,
    vertex_offset: int,
    vertex_group_bone_indices: dict[int, int],
    fallback_weight_bone_index: int,
) -> list['Psk.Weight']:
    """
    Build PSK vertex weights from the mesh's vertex groups.
    """
    V = len(mesh_data.vertices)

    # Single O(V) pass: collect all raw influence records.
    v_indices_list  = []
    vg_indices_list = []
    weights_list    = []

    for vertex_index, vertex in enumerate(mesh_data.vertices):
        for group_element in vertex.groups:
            if group_element.weight > 0.0:
                v_indices_list.append(vertex_index)
                vg_indices_list.append(group_element.group)
                weights_list.append(group_element.weight)

    if not v_indices_list:
        # No weights at all – assign everything to the fallback bone.
        weights = []
        for vertex_index in range(V):
            w = Psk.Weight()
            w.bone_index = fallback_weight_bone_index
            w.point_index = vertex_offset + vertex_index
            w.weight = 1.0
            weights.append(w)
        return weights

    v_indices  = np.array(v_indices_list,  dtype=np.int32)
    vg_indices = np.array(vg_indices_list, dtype=np.int32)
    raw_weights = np.array(weights_list,   dtype=np.float32)

    # Because the vertex groups may contain entries for which there is no matching bone in the armature,
    # we must filter them out and not export any weights for these vertex groups.
    max_vg = int(vg_indices.max()) + 1
    vg_to_bone_map = np.full(max_vg, -1, dtype=np.int32)
    for vg_idx, bone_idx in vertex_group_bone_indices.items():
        if vg_idx < max_vg:
            vg_to_bone_map[vg_idx] = bone_idx

    bone_indices = vg_to_bone_map[vg_indices]  # (N,)
    valid_mask   = bone_indices >= 0
    v_indices    = v_indices[valid_mask]
    bone_indices = bone_indices[valid_mask]
    raw_weights  = raw_weights[valid_mask]

    # Keep track of which vertices have been assigned weights.
    # The ones that have not been assigned weights will be assigned to the root bone.
    # Without this, some older versions of UnrealEd may have corrupted meshes.
    has_weight = np.zeros(V, dtype=bool)
    if len(v_indices):
        has_weight[v_indices] = True

    weights = []
    for i in range(len(v_indices)):
        w = Psk.Weight()
        w.bone_index  = int(bone_indices[i])
        w.point_index = vertex_offset + int(v_indices[i])
        w.weight      = float(raw_weights[i])
        weights.append(w)

    # Assign vertices that have not been assigned weights to the root bone of the armature.
    unweighted = np.where(~has_weight)[0]
    for vertex_index in unweighted:
        w = Psk.Weight()
        w.bone_index  = fallback_weight_bone_index
        w.point_index = vertex_offset + int(vertex_index)
        w.weight      = 1.0
        weights.append(w)

    return weights


def build_psk(context: Context, input_objects: PskInputObjects, options: PskBuildOptions) -> PskBuildResult:

    assert context.window_manager

    armature_objects = list(input_objects.armature_objects)
    armature_object_tree = ObjectTree(input_objects.armature_objects)

    warnings: list[str] = []
    psk = Psk()

    psx_bone_create_result = create_psx_bones(
        armature_objects=armature_objects,
        export_space=options.export_space,
        forward_axis=options.forward_axis,
        up_axis=options.up_axis,
        scale=options.scale,
        bone_filter_mode=options.bone_filter_mode,
        bone_collection_indices=options.bone_collection_indices
    )

    psk.bones = [bone.psx_bone for bone in psx_bone_create_result.bones]

    if len(psk.bones) == 0:
        # Add a default root bone if there are no bones to export.
        # This is necessary because Unreal Engine requires at least one bone in the PSK file.
        psx_bone = PsxBone()
        psx_bone.name = b'ROOT'
        psx_bone.rotation = convert_bpy_quaternion_to_psx_quaternion(Quaternion())
        psk.bones.append(psx_bone)

    # Materials
    mesh_objects = [dfs_object.obj for dfs_object in input_objects.mesh_dfs_objects]

    match options.material_order_mode:
        case 'AUTOMATIC':
            materials = list(get_materials_for_mesh_objects(context.evaluated_depsgraph_get(), mesh_objects))
        case 'MANUAL':
            # The material name list may contain materials that are not on the mesh objects.
            # Therefore, we can take the material_name_list as gospel and simply use it as a lookup table.
            # If a look-up fails, replace it with an empty material.
            materials = [bpy.data.materials.get(x, None) for x in options.material_name_list]

            # Check if any mesh needs a None material (has no slots or empty slots)
            needs_none_material = False
            for mesh_object in mesh_objects:
                evaluated_mesh_object = mesh_object.evaluated_get(context.evaluated_depsgraph_get())
                if len(evaluated_mesh_object.material_slots) == 0:
                    needs_none_material = True
                    break
                for material_slot in evaluated_mesh_object.material_slots:
                    if material_slot.material is None:
                        needs_none_material = True
                        break
                if needs_none_material:
                    break

            # Append None at the end if needed and not already present
            if needs_none_material and None not in materials:
                materials.append(None)
        case _:
            assert False, f'Invalid material order mode: {options.material_order_mode}'

    for material in materials:
        psk_material = Psk.Material()
        psk_material.name = convert_string_to_cp1252_bytes(material.name if material else 'None')
        psk_material.texture_index = len(psk.materials)
        if material is not None:
            psk_material.poly_flags = triangle_type_and_bit_flags_to_poly_flags(material.psk.mesh_triangle_type,
                                                                                material.psk.mesh_triangle_bit_flags)
        psk.materials.append(psk_material)

    # Ensure at least one material exists
    if len(psk.materials) == 0:
        # Add a default material if no materials are present.
        psk_material = Psk.Material()
        psk_material.name = convert_string_to_cp1252_bytes('None')
        psk.materials.append(psk_material)

    context.window_manager.progress_begin(0, len(input_objects.mesh_dfs_objects))
    coordinate_system_matrix = get_coordinate_system_transform(options.forward_axis, options.up_axis)
    root_armature_object = next(iter(armature_object_tree), None)

    # Calculate the export spaces for the armature objects.
    # This is used later to transform the mesh object geometry into the export space.
    armature_mesh_export_space_matrices: dict[Object | None, Matrix] = {None: Matrix.Identity(4)}

    if options.export_space == 'ARMATURE':
        # For meshes without an armature modifier, we need to set the export space to the first armature object.
        armature_mesh_export_space_matrices[None] = _get_mesh_export_space_matrix(root_armature_object, options.export_space)

    # TODO: also handle the case of multiple roots; dont' just assume we have one!
    for armature_node in iter(armature_object_tree):
        armature_mesh_export_space_matrices[armature_node.object] = _get_mesh_export_space_matrix(armature_node, options.export_space)

    # Temporarily force the armature into the rest position.
    # The original pose position setting will be restored at the end.
    original_armature_object_pose_positions = {a: a.data.pose_position for a in armature_objects}
    for armature_object in armature_objects:
        armature_data = typing_cast(Armature, armature_object.data)
        armature_data.pose_position = 'REST'

    material_names = [m.name if m is not None else 'None' for m in materials]

    scale_matrix = Matrix.Scale(options.scale, 4)

    for object_index, input_mesh_object in enumerate(input_objects.mesh_dfs_objects):
        obj, matrix_world = input_mesh_object.obj, input_mesh_object.matrix_world
        armature_object = get_armature_for_mesh_object(obj)
        should_flip_normals = False

        # Material indices
        material_indices = list(_get_material_name_indices(obj, material_names))

        if len(material_indices) == 0:
            # If the mesh has no material slots, map to the 'None' material index
            try:
                none_material_index = material_names.index('None')
            except ValueError:
                none_material_index = 0
            material_indices = [none_material_index]

        # Store the reference to the evaluated object and data so that we can clean them up later.
        evaluated_mesh_object = None
        evaluated_mesh_data = None

        # Mesh data
        match options.object_eval_state:
            case 'ORIGINAL':
                mesh_object = obj
                mesh_data = typing_cast(Mesh, obj.data)
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
                mesh_object = evaluated_mesh_object
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

        match options.export_space:
            case 'ARMATURE' | 'ROOT':
                mesh_export_space_matrix = armature_mesh_export_space_matrices[armature_object]
            case 'WORLD':
                mesh_export_space_matrix = armature_mesh_export_space_matrices[armature_object]
            case _:
                assert False, f'Invalid export space: {options.export_space}'

        vertex_transform_matrix = scale_matrix @ coordinate_system_matrix.inverted() @ mesh_export_space_matrix
        point_transform_matrix = vertex_transform_matrix @ mesh_object.matrix_world

        # Vertices
        vertex_offset = len(psk.points)
        V = len(mesh_data.vertices)

        co_flat = np.empty(V * 3, dtype=np.float32)
        mesh_data.vertices.foreach_get("co", co_flat)

        point_transform_np = _matrix_to_numpy(point_transform_matrix)
        transformed = _transform_vertices_numpy(co_flat, point_transform_np)  # (V, 3)

        for i in range(V):
            point = Vector3()
            point.x = float(transformed[i, 0])
            point.y = float(transformed[i, 1])
            point.z = float(transformed[i, 2])
            psk.points.append(point)

        # Wedges
        mesh_data.calc_loop_triangles()

        if mesh_data.uv_layers.active is None:
            warnings.append(f'"{mesh_object.name}" has no active UV Map')

        wedge_index_offset = len(psk.wedges)
        unique_wedges, loop_wedge_indices = _build_wedges_numpy(
            mesh_data, vertex_offset, material_indices
        )
        psk.wedges.extend(unique_wedges)

        # Faces
        psk_face_start_index = len(psk.faces)
        new_faces = _build_faces_numpy(
            mesh_data, loop_wedge_indices, wedge_index_offset, material_indices
        )
        psk.faces.extend(new_faces)

        if should_flip_normals:
            # Invert the normals of the faces.
            for face in psk.faces[psk_face_start_index:]:
                face.wedge_indices = (face.wedge_indices[2], face.wedge_indices[1], face.wedge_indices[0])

        # Weights
        if armature_object is not None:
            armature_data = typing_cast(Armature, armature_object.data)
            bone_index_offset = psx_bone_create_result.armature_object_root_bone_indices[armature_object]

            # Because the vertex groups may contain entries for which there is no matching bone in the armature,
            # we must filter them out and not export any weights for these vertex groups.
            bone_names = psx_bone_create_result.armature_object_bone_names[armature_object]
            vertex_group_names = [x.name for x in mesh_object.vertex_groups]
            vertex_group_bone_indices: dict[int, int] = dict()
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

            fallback_weight_bone_index = psx_bone_create_result.armature_object_root_bone_indices[armature_object]
            new_weights = _build_weights_numpy(
                mesh_data,
                mesh_object,
                vertex_offset,
                vertex_group_bone_indices,
                fallback_weight_bone_index,
            )
            psk.weights.extend(new_weights)

        if evaluated_mesh_object is not None:
            bpy.data.objects.remove(mesh_object)
            del mesh_object

        if evaluated_mesh_data is not None:
            bpy.data.meshes.remove(mesh_data)
            del mesh_data

        context.window_manager.progress_update(object_index)

    # Restore the original pose position of the armature objects.
    for armature_object, pose_position in original_armature_object_pose_positions.items():
        armature_data = typing_cast(Armature, armature_object.data)
        armature_data.pose_position = pose_position

    # https://github.com/DarklightGames/io_scene_psk_psa/issues/129.
    psk.sort_and_normalize_weights()

    context.window_manager.progress_end()

    return PskBuildResult(psk, warnings)