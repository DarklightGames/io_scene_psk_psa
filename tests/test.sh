# usr/bin/env bash
# This file is meant to be executed from inside a Docker container.
# To run tests on the host system, use the `test.sh` script in the root directory.
export BLENDER_EXECUTABLE=$(cat /blender_executable_path)
pytest --cov-report xml --cov=/root/.config/blender -svv tests --blender-executable $BLENDER_EXECUTABLE --blender-addons-dirs ../addons
# Fixes the paths in the coverage report to be relative to the current directory.
sed -i 's|/root/.config/blender||g' coverage.xml
sed -i 's|5.0/scripts/addons/io_scene_psk_psa/||g' coverage.xml
