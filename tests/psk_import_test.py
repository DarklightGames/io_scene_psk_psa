import bpy
import pytest

SUZANNE_FILEPATH = 'tests/data/Suzanne.psk'
SARGE_FILEPATH = 'tests/data/CS_Sarge_S0_Skelmesh.pskx'
SLURP_MONSTER_AXE_FILEPATH = 'tests/data/Slurp_Monster_Axe_LOD0.psk'
BAT_FILEPATH = 'tests/data/Bat.psk'


@pytest.fixture(autouse=True)
def run_before_and_after_Tests(tmpdir):
    # Setup: Run before the tests
    bpy.ops.wm.read_homefile(app_template='')
    yield
    # Teardown: Run after the tests
    pass


def test_psk_import_all():
    assert bpy.ops.psk.import_file(
        filepath=SUZANNE_FILEPATH,
        components='ALL',
        ) == {'FINISHED'}

    armature_object = bpy.data.objects.get('Suzanne', None)

    assert armature_object is not None, "Armature object not found in the scene"
    assert armature_object.type == 'ARMATURE', "Armature object type should be ARMATURE"
    assert armature_object is not None, "Armature object not found in the scene"
    assert len(armature_object.children) == 1, "Armature object should have one child"

    armature_data = armature_object.data

    assert len(armature_data.bones) == 1, "Armature should have one bone"

    mesh_object = bpy.data.objects.get('Suzanne.001', None)
    assert mesh_object is not None, "Mesh object not found in the scene"

    mesh_data = mesh_object.data

    assert len(mesh_data.vertices) == 507
    assert len(mesh_data.polygons) == 968


def test_psk_import_armature_only():
    assert bpy.ops.psk.import_file(
        filepath=SUZANNE_FILEPATH,
        components='ARMATURE',
        ) == {'FINISHED'}

    armature_object = bpy.data.objects.get('Suzanne', None)

    assert armature_object.type == 'ARMATURE', "Armature object type should be ARMATURE"
    assert armature_object is not None, "Armature object not found in the scene"
    assert len(armature_object.children) == 0, "Armature object should have no children"

    armature_data = armature_object.data

    assert len(armature_data.bones) == 1, "Armature should have one bone"


def test_psk_import_mesh_only():
    assert bpy.ops.psk.import_file(
        filepath=SUZANNE_FILEPATH,
        components='MESH',
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('Suzanne', None)
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"
    assert mesh_object is not None, "Mesh object not found in the scene"

    mesh_data = mesh_object.data

    assert len(mesh_data.vertices) == 507
    assert len(mesh_data.polygons) == 968


def test_psk_import_scale():
    """
    Test the import of a PSK file with a scale factor of 2.0.
    The scale factor is applied to the armature object.
    """
    assert bpy.ops.psk.import_file(
        filepath=SUZANNE_FILEPATH,
        components='ALL',
        scale=2.0,
        ) == {'FINISHED'}

    armature_object = bpy.data.objects.get('Suzanne', None)
    assert armature_object is not None, "Armature object not found in the scene"
    assert armature_object.type == 'ARMATURE', "Armature object type should be ARMATURE"
    assert tuple(armature_object.scale) == (2.0, 2.0, 2.0), "Armature object scale should be (2.0, 2.0, 2.0)"


def test_psk_import_bone_length():
    bone_length = 1.25

    assert bpy.ops.psk.import_file(
        filepath=SUZANNE_FILEPATH,
        components='ARMATURE',
        bone_length=bone_length,
        ) == {'FINISHED'}
    
    armature_object = bpy.data.objects.get('Suzanne', None)
    assert armature_object is not None, "Armature object not found in the scene"
    assert armature_object.type == 'ARMATURE', "Armature object type should be ARMATURE"

    armature_data = armature_object.data
    assert armature_data is not None, "Armature data not found in the scene"
    assert len(armature_data.bones) == 1, "Armature should have one bone"
    assert 'ROOT' in armature_data.bones, "Armature should have a bone named 'ROOT'"

    root_bone = armature_data.bones['ROOT']
    assert tuple(root_bone.head) == (0.0, 0.0, 0.0), "Bone head should be (0.0, 0.0, 0.0)"
    assert tuple(root_bone.tail) == (0.0, bone_length, 0.0), f"Bone tail should be (0.0, {bone_length}, 0.0)"


def test_psk_import_with_vertex_normals():
    assert bpy.ops.psk.import_file(
        filepath=SARGE_FILEPATH,
        components='MESH',
        should_import_vertex_normals=True,
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('CS_Sarge_S0_Skelmesh', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"

    mesh_data = mesh_object.data
    assert mesh_data is not None, "Mesh data not found in the scene"
    assert mesh_data.has_custom_normals, "Mesh should have custom normals"


def test_psk_import_without_vertex_normals():
    assert bpy.ops.psk.import_file(
        filepath=SARGE_FILEPATH,
        components='MESH',
        should_import_vertex_normals=False,
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('CS_Sarge_S0_Skelmesh', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"

    mesh_data = mesh_object.data
    assert mesh_data is not None, "Mesh data not found in the scene"
    assert not mesh_data.has_custom_normals, "Mesh should not have custom normals"


def test_psk_import_with_vertex_colors_srgba():
    assert bpy.ops.psk.import_file(
        filepath=SARGE_FILEPATH,
        components='MESH',
        should_import_vertex_colors=True,
        vertex_color_space='SRGBA',
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('CS_Sarge_S0_Skelmesh', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"

    mesh_data = mesh_object.data
    assert mesh_data is not None, "Mesh data not found in the scene"
    assert len(mesh_data.color_attributes) == 1, "Mesh should have one vertex color layer"
    assert mesh_data.color_attributes[0].name == 'VERTEXCOLOR', "Vertex color layer should be named 'VERTEXCOLOR'"
    assert tuple(mesh_data.color_attributes[0].data[3303].color) == (0.34586891531944275, 0.0, 0.0, 1.0), "Unexpected vertex color value"


def test_psk_import_vertex_colors_linear():
    assert bpy.ops.psk.import_file(
        filepath=SARGE_FILEPATH,
        components='MESH',
        should_import_vertex_colors=True,
        vertex_color_space='LINEAR',
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('CS_Sarge_S0_Skelmesh', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"

    mesh_data = mesh_object.data
    assert mesh_data is not None, "Mesh data not found in the scene"
    assert len(mesh_data.color_attributes) == 1, "Mesh should have one vertex color layer"
    assert mesh_data.color_attributes[0].name == 'VERTEXCOLOR', "Vertex color layer should be named 'VERTEXCOLOR'"
    assert tuple(mesh_data.color_attributes[0].data[3303].color) == (0.09803921729326248, 0.0, 0.0, 1.0), "Unexpected vertex color value"


def test_psk_import_without_vertex_colors():
    assert bpy.ops.psk.import_file(
        filepath=SARGE_FILEPATH,
        components='MESH',
        should_import_vertex_colors=False,
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('CS_Sarge_S0_Skelmesh', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"

    mesh_data = mesh_object.data
    assert mesh_data is not None, "Mesh data not found in the scene"
    assert len(mesh_data.color_attributes) == 0, "Mesh should not have any vertex color layers"


def test_psk_import_extra_uvs():
    assert bpy.ops.psk.import_file(
        filepath=SARGE_FILEPATH,
        components='MESH',
        should_import_vertex_colors=True,
        vertex_color_space='LINEAR',
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('CS_Sarge_S0_Skelmesh', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"

    mesh_data = mesh_object.data
    assert mesh_data is not None, "Mesh data not found in the scene"
    assert len(mesh_data.uv_layers) == 2, "Mesh should have two UV layers"

    assert mesh_data.uv_layers[0].name == 'UVMap', "First UV layer should be named 'UVMap'"
    assert mesh_data.uv_layers[1].name == 'EXTRAUV0', "Second UV layer should be named 'EXTRAUV0'"

    # Verify that the data is actually different
    assert mesh_data.uv_layers[0].uv[0].vector.x == 0.92480468750
    assert mesh_data.uv_layers[0].uv[0].vector.y == 0.90533447265625
    assert mesh_data.uv_layers[1].uv[0].vector.x == 3.0517578125e-05
    assert mesh_data.uv_layers[1].uv[0].vector.y == 0.999969482421875


def test_psk_import_materials():
    assert bpy.ops.psk.import_file(
        filepath=SARGE_FILEPATH,
        components='MESH',
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('CS_Sarge_S0_Skelmesh', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"

    mesh_data = mesh_object.data

    assert mesh_data is not None, "Mesh data not found in the scene"
    assert len(mesh_data.materials) == 4, "Mesh should have four materials"
    material_names = (
        'CS_Sarge_S0_MI',
        'TP_Core_Eye_MI',
        'AB_Sarge_S0_E_StimPack_MI1',
        'CS_Sarge_S0_MI'
    )
    for i, material in enumerate(mesh_data.materials):
        assert material.name == material_names[i], f"Material {i} name should be {material_names[i]}"


def test_psk_import_shape_keys():
    assert bpy.ops.psk.import_file(
        filepath=SLURP_MONSTER_AXE_FILEPATH,
        components='MESH',
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('Slurp_Monster_Axe_LOD0', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"
    assert mesh_object.data.shape_keys is not None, "Mesh object should have shape keys"

    shape_key_names = (
        'MORPH_BASE',
        'pickaxe',
        'axe',
        'Blob_03',
        'Blob02',
        'Blob01',
    )
    shape_keys = mesh_object.data.shape_keys.key_blocks
    assert len(shape_keys) == 6, "Mesh object should have 6 shape keys"
    for i, shape_key in enumerate(shape_keys):
        assert shape_key.name == shape_key_names[i], f"Shape key {i} name should be {shape_key_names[i]}"

def test_psk_import_without_shape_keys():
    assert bpy.ops.psk.import_file(
        filepath=SLURP_MONSTER_AXE_FILEPATH,
        components='MESH',
        should_import_shape_keys=False,
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('Slurp_Monster_Axe_LOD0', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"
    assert mesh_object.data.shape_keys is None, "Mesh object should not have shape keys"


def test_psk_import_with_invalid_faces():
    assert bpy.ops.psk.import_file(
        filepath=BAT_FILEPATH,
        components='MESH'
        ) == {'FINISHED'}
