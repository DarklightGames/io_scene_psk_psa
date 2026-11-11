import bpy  # noqa: F401 -- Must be imported first; it puts Blender's bundled modules on `sys.path`.
import addon_utils
import pytest


@pytest.fixture(scope='session', autouse=True)
def enable_addon():
    assert addon_utils.enable('io_scene_psk_psa', default_set=True, handle_error=None) is not None
