import bpy
import pytest
from psk_psa_py.psa.reader import read_psa

SHREK_PSK_FILEPATH = 'tests/data/Shrek.psk'
SHREK_PSA_FILEPATH = 'tests/data/Shrek.psa'
BROADSWORD_PSK_FILEPATH = 'tests/data/WEP_BroadSword_SKEL.psk'
BROADSWORD_PSA_FILEPATH = 'tests/data/WEP_BroadSword_ANIM.psa'


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


def test_psa_import_convert_to_samples():
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

    # Import the associated PSA file with import_all operator, and convert to samples.
    assert bpy.ops.psa.import_all(
        filepath=SHREK_PSA_FILEPATH,
        should_convert_to_samples=True
        ) == {'FINISHED'}, "PSA import failed."
    
    # TODO: More thorough tests on the imported data for the animations.
    EXPECTED_ACTION_COUNT = 135
    assert len(bpy.data.actions) == EXPECTED_ACTION_COUNT, \
        f"Expected {EXPECTED_ACTION_COUNT} actions, but found {len(bpy.data.actions)}."


def test_psa_import_resampling():
    assert bpy.ops.psk.import_file(
        filepath=BROADSWORD_PSK_FILEPATH,
        components='ALL'
    ) == {'FINISHED'}, "PSK import failed"

    armature_object = bpy.data.objects.get('WEP_BroadSword_SKEL', None)
    assert armature_object is not None, "Armature object not found in the scene."
    assert armature_object.type == 'ARMATURE', "Object is not of type ARMATURE."

    # Select the armature object
    bpy.context.view_layer.objects.active = armature_object
    armature_object.select_set(True)

    # Set the scene FPS to differ from that of the sequence's FPS.
    assert bpy.context.scene is not None
    bpy.context.scene.render.fps = 33.3

    # Ensure that we will in fact trigger the resampling.
    psa = read_psa(open(BROADSWORD_PSA_FILEPATH, 'rb'))
    assert len(psa.sequences) > 0
    for sequence in psa.sequences.values():
        assert sequence.fps != bpy.context.scene.render.fps

    assert bpy.ops.psa.import_all(
        filepath=BROADSWORD_PSA_FILEPATH,
        fps_source='SCENE'
    ) == {'FINISHED'}, "PSA import failed"
