import bpy
import pytest

SARGE_IMPORT_FILEPATH = 'tests/data/CS_Sarge_S0_Skelmesh.pskx'
SARGE_EXPORT_FILEPATH = 'Sarge_vertexNorms.psk'
SARGE_REIMPORT_FILEPATH = 'Sarge_vertexNorms.pskx'

@pytest.fixture(autouse=True)
def run_before_and_after_Tests():
    # Setup: Run before the tests
    bpy.ops.wm.read_homefile(app_template='')
    yield
    # Teardown: Run after the tests
    pass

def test_psk_export_with_vertex_normals(tmp_path):
    # import a model with custom vertex norms
    bpy.ops.psk.import_file(
        filepath=SARGE_IMPORT_FILEPATH,
        components='MESH',
        should_import_vertex_normals=True)

    # select the mesh so the operator can target it
    bpy.data.objects.get('CS_Sarge_S0_Skelmesh', None).select_set(True)
    
    # set the options to ensure the operator does what we want
    bpy.context.scene.psk_export.export_vertex_normals = True

    # export it WITH vertex norms
    assert bpy.ops.psk.export(
        filepath= tmp_path / SARGE_EXPORT_FILEPATH,
        ) == {'FINISHED'}, "PSK export failed."

    # re import it (noting that it changed the extension to PSKX)
    assert bpy.ops.psk.import_file(
        filepath= tmp_path / SARGE_REIMPORT_FILEPATH,
        components='MESH',
        should_import_vertex_normals=True,
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('CS_Sarge_S0_Skelmesh_exportVertexNorms', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"

    mesh_data = mesh_object.data
    assert mesh_data is not None, "Mesh data not found in the scene"
    assert mesh_data.has_custom_normals, "Mesh should have custom normals"

def test_psk_export_without_vertex_normals(tmp_path):
    # import a model with custom vertex norms
    bpy.ops.psk.import_file(
        filepath=SARGE_IMPORT_FILEPATH,
        components='MESH',
        should_import_vertex_normals=True)

    # select the mesh so the operator can target it
    bpy.data.objects.get('CS_Sarge_S0_Skelmesh', None).select_set(True)
    
    # set the options to ensure the operator does what we want
    bpy.context.scene.psk_export.export_vertex_normals = False

    # export it WITHOUT vertex norms
    assert bpy.ops.psk.export(
        filepath=tmp_path / SARGE_EXPORT_FILEPATH,
        ) == {'FINISHED'}, "PSK export failed."

    # re import it (note that it did not add the x to the filepath)
    assert bpy.ops.psk.import_file(
        filepath=tmp_path / SARGE_EXPORT_FILEPATH,
        components='MESH',
        should_import_vertex_normals=True,
        ) == {'FINISHED'}

    mesh_object = bpy.data.objects.get('CS_Sarge_S0_Skelmesh_exportVertexNorms', None)
    assert mesh_object is not None, "Mesh object not found in the scene"
    assert mesh_object.type == 'MESH', "Mesh object type should be MESH"

    mesh_data = mesh_object.data
    assert mesh_data is not None, "Mesh data not found in the scene"
    assert not mesh_data.has_custom_normals, "Mesh should not have custom normals"
