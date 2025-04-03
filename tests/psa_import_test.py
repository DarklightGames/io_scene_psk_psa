import bpy
import pytest

SHREK_PSK_FILEPATH = 'tests/data/Shrek.psk'
SHREK_PSA_FILEPATH = 'tests/data/Shrek.psa'


@pytest.fixture(autouse=True)
def run_before_and_after_Tests(tmpdir):
    # Setup: Run before the tests
    bpy.ops.wm.read_homefile(app_template='')
    yield
    # Teardown: Run after the tests
    pass


def test_psa_import_all():
    assert bpy.ops.psk.import_file(
        filepath=SHREK_PSK_FILEPATH,
        components='ALL',
        ) == {'FINISHED'}, "PSK import failed."

    armature_object = bpy.data.objects.get('Shrek', None)
    assert armature_object is not None, "Armature object not found in the scene."
    assert armature_object.type == 'ARMATURE', "Object is not of type ARMATURE."

    # Select the armature object
    bpy.context.view_layer.objects.active = armature_object
    armature_object.select_set(True)

    # Import the associated PSA file with import_all operator.
    assert bpy.ops.psa.import_all(
        filepath=SHREK_PSA_FILEPATH
        ) == {'FINISHED'}, "PSA import failed."
    
    # TODO: More thorough tests on the imported data for the animations.
    EXPECTED_ACTION_COUNT = 135
    assert len(bpy.data.actions) == EXPECTED_ACTION_COUNT, \
        f"Expected {EXPECTED_ACTION_COUNT} actions, but found {len(bpy.data.actions)}."
