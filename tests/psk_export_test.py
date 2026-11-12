import tempfile

import bpy
import pytest
from psk_psa_py.psk.reader import read_psk_from_file


@pytest.fixture(autouse=True)
def run_before_and_after_tests(tmpdir):
    # Setup: Run before the tests
    bpy.ops.wm.read_homefile(filepath='tests/data/psk_export_tests.blend')

    yield
    # Teardown: Run after the tests


def export_psk_and_read_back(collection_name: str):
    collection = bpy.data.collections.get(collection_name, None)
    assert collection is not None, f'Collection {collection_name} not found in the scene.'

    # Select the collection to make it the active collection.
    view_layer = bpy.context.view_layer
    assert view_layer is not None, 'No active view layer found.'
    view_layer.active_layer_collection = view_layer.layer_collection.children[collection_name]

    filepath = str(tempfile.gettempdir() + f'/{collection_name}.psk')

    collection.exporters[0].filepath = filepath

    assert bpy.ops.collection.exporter_export() == {'FINISHED'}, 'PSK export failed.'

    # Now load the exported PSK file and return its contents.
    psk = read_psk_from_file(filepath)
    return psk


def test_psk_export_cube_no_bones():
    psk = export_psk_and_read_back('cube_no_bones')

    # There should be one bone when no armature is present, this is added automatically to serve as the root bone for the mesh.
    assert len(psk.bones) == 1, f'Expected 1 bone, but found {len(psk.bones)}.'
    assert len(psk.points) == 8, f'Expected 8 points, but found {len(psk.points)}.'
    assert len(psk.faces) == 12, f'Expected 12 faces, but found {len(psk.faces)}.'
    assert len(psk.materials) == 1, f'Expected 1 material, but found {len(psk.materials)}.'


def test_cube_edge_split():
    # The cube has all the edges set to split with a modifier.
    psk = export_psk_and_read_back('cube_edge_split')

    assert len(psk.bones) == 1, f'Expected 1 bone, but found {len(psk.bones)}.'
    assert len(psk.points) == 24, f'Expected 24 points, but found {len(psk.points)}.'
    assert len(psk.faces) == 12, f'Expected 12 faces, but found {len(psk.faces)}.'
    assert len(psk.materials) == 1, f'Expected 1 material, but found {len(psk.materials)}.'


def test_cube_with_simple_armature():
    # The cube has all the edges set to split with a modifier.
    psk = export_psk_and_read_back('cube_with_simple_armature')

    assert len(psk.bones) == 1, f'Expected 1 bone, but found {len(psk.bones)}.'
    assert psk.bones[0].name == b'ROOT', f"Expected bone name 'ROOT', but found {psk.bones[0].name}."


def set_manual_material_list(collection_name: str, items: list[tuple[str, str]]):
    collection = bpy.data.collections[collection_name]
    export_properties = collection.exporters[0].export_properties
    export_properties.material_order_mode = 'MANUAL'
    export_properties.material_name_list.clear()
    for material_name, export_name in items:
        item = export_properties.material_name_list.add()
        item.material_name = material_name
        item.export_name = export_name


def test_psk_export_material_export_name():
    set_manual_material_list('cube_no_bones', [('Material', 'Renamed')])
    psk = export_psk_and_read_back('cube_no_bones')

    assert [m.name for m in psk.materials] == [b'Renamed']
    assert all(face.material_index == 0 for face in psk.faces)


def test_psk_export_material_empty_export_name_uses_material_name():
    set_manual_material_list('cube_no_bones', [('Material', '')])
    psk = export_psk_and_read_back('cube_no_bones')

    assert [m.name for m in psk.materials] == [b'Material']


def test_psk_export_material_list_populate_keeps_export_names():
    from io_scene_psk_psa.psk.export.operators import populate_material_name_list

    set_manual_material_list('cube_no_bones', [('Material', 'Renamed')])
    collection = bpy.data.collections['cube_no_bones']
    material_list = collection.exporters[0].export_properties.material_name_list
    mesh_objects = [x for x in collection.all_objects if x.type == 'MESH']

    populate_material_name_list(bpy.context.evaluated_depsgraph_get(), mesh_objects, material_list)

    assert [(x.material_name, x.export_name) for x in material_list] == [('Material', 'Renamed')]


def test_psk_export_material_list_populate_fills_empty_export_names():
    from io_scene_psk_psa.psk.export.operators import populate_material_name_list

    set_manual_material_list('cube_no_bones', [('Material', '')])
    collection = bpy.data.collections['cube_no_bones']
    material_list = collection.exporters[0].export_properties.material_name_list
    mesh_objects = [x for x in collection.all_objects if x.type == 'MESH']

    populate_material_name_list(bpy.context.evaluated_depsgraph_get(), mesh_objects, material_list)

    assert [(x.material_name, x.export_name) for x in material_list] == [('Material', 'Material')]
