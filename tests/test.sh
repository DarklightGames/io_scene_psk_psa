#!/usr/bin/env bash
# This file is meant to be executed from inside a Docker container.
# To run tests on the host system, use the `test.sh` script in the root directory.
BLENDER_EXECUTABLE=$(cat /blender_executable_path)
uv run --no-sync pytest --cov-report xml --cov=/root/.config/blender -svv tests --blender-executable "$BLENDER_EXECUTABLE" --blender-addons-dirs ../addons
PYTEST_EXIT_CODE=$?
# Fixes the paths in the coverage report to be relative to the current directory.
sed -i 's|/root/.config/blender||g' coverage.xml
sed -i -E 's|[0-9]+\.[0-9]+/scripts/addons/io_scene_psk_psa/||g' coverage.xml
exit $PYTEST_EXIT_CODE
