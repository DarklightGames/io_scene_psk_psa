import os
import subprocess
from fnmatch import fnmatch
from zipfile import ZipFile, ZIP_DEFLATED

ignore_patterns = [
    '*/__pycache__/*',
    '*/.git/*',
    '*/.github/*',
    '*/.idea/*',
    '*/venv/*',
    '*/.gitignore',
    '*/.gitattributes',
    '*/build/*',
    '*/build.py',
]


def zipdir(path, zip_file: ZipFile):
    for root, dirs, files in os.walk(path):
        for file in files:
            if file != zip_file.filename and not any(fnmatch(os.path.join(root, file), pattern) for pattern in ignore_patterns):
                zip_file.write(os.path.join(root, file))

# Get the branch name.
branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode('utf-8').strip()

# Get the most recent tag.
tag = subprocess.check_output(['git', 'describe', '--tags', '--abbrev=0']).decode('utf-8').strip()

# Create a zip file of the current directory.

zip_path = f'./build/io_scene_psk_psa-{branch}-{tag}.zip'

# Check that the directory exists, if it doesn't, create it.
if not os.path.exists('./build'):
    os.makedirs('./build')

zipf = ZipFile(zip_path, 'w', ZIP_DEFLATED)
zipdir('.', zipf)
zipf.close()
