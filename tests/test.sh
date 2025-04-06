# This file is meant to be executed inside a Docker container.
export BLENDER_EXECUTABLE=$(cat /blender_executable_path)
pytest --cov-report xml --cov=/root/.config/blender -svv tests --blender-executable $BLENDER_EXECUTABLE --blender-addons-dirs ../addons
# Fixes the paths in the coverage report to be relative to the current directory.
sed -i 's|/root/.config/blender||g' coverage.xml
sed -i 's|4.4/scripts/addons/io_scene_psk_psa/||g' coverage.xml
