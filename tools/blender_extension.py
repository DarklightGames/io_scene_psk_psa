"""
Equivalent of `blender --command extension ...`, using the `bpy` Python module
instead of a Blender executable.

Usage (from the repository root):
    uv run tools/blender_extension.py build --source-dir io_scene_psk_psa --output-dir dist
    uv run tools/blender_extension.py validate io_scene_psk_psa
"""

import sys

import bpy  # noqa: F401 -- Importing `bpy` puts Blender's bundled scripts on `sys.path`.
from bl_pkg.bl_extension_cli import cli_extension_handler  # type: ignore

if __name__ == '__main__':
    sys.exit(cli_extension_handler(sys.argv[1:]))
