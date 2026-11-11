import os

import bpy


def test_blender_version_is_expected():
    # Set by `uv run test` (`tools/test.py`); otherwise, the default (newest) version is expected.
    expected = os.environ.get('EXPECTED_BLENDER_VERSION')
    if expected is None:
        from tools.blender_versions import get_supported_blender_versions
        expected = get_supported_blender_versions()[-1].name
    actual = '{}.{}'.format(*bpy.app.version[:2])
    assert actual == expected, f'Expected to be running Blender {expected}, but running Blender {actual}'
