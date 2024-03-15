import ast
import glob
import os

# Walk the directory and open all .py files using glob
strings = set()
for file in glob.glob('../io_scene_psk_psa/**/*.py', recursive=True):
    print(file)
    with open(os.path.join(file), 'r') as f:
        if file.endswith('i18n.py'):
            # TODO: Don't parse the i18n files.
            continue
        # Walk the entire tree and build a list of all string literals.
        try:
            a = ast.parse(f.read())
            for node in ast.walk(a):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    strings.add(node.s)
        except UnicodeDecodeError as e:
            print(f'Error reading file {file}: {e}')

# Remove all strings that are empty or contain only whitespace.
strings = set(filter(lambda x: x.strip(), strings))

# Remove all strings that have no alphabetic characters.
strings = set(filter(lambda x: any(c.isalpha() for c in x), strings))

# Remove any strings that have '@return: ' in them.
strings = set(filter(lambda x: '@return: ' not in x, strings))

# Remove any strings that are entirely lowercase and have no whitespace.
strings = set(filter(lambda x: not x.islower() or ' ' in x, strings))

# Remove any strings that are in SCREAMING_SNAKE_CASE.
strings = set(filter(lambda x: not x.isupper(), strings))

# Remove any strings that have underscores.
strings = set(filter(lambda x: '_' not in x, strings))

# Remove any string that starts with a newline.
strings = set(filter(lambda x: not x.startswith('\n'), strings))

# Remove any string that looks like a regular expression.
strings = set(filter(lambda x: not any(c in x for c in '^'), strings))

# Convert the set to a list and sort it.
strings = list(strings)
strings.sort()

def write_multiline_string(f, string):
    f.write(f'msgid ""\n')
    for line in string.split('\n'):
        f.write(f'"{line}"\n')
    f.write('msgstr ""\n\n')

# TODO: big brain move would be to load the translated Blender strings and remove any that are already translated
# instead of manually removing them.
exclude_strings = {
    'Import-Export',
    'Linear',
    'Masked',
    'Normal',
    'Placeholder',
    'Flat',
    'Environment',
    'Advanced',
    'Action',
    'All',
    'Assets',
    'Armature',
    'Materials'
    'Bones',
    'Custom',
    'Data',
    'Colin Basnett, Yurii Ti',
    'Invert',
    'Keyframes', # maybe?
    'Mesh',
    'None',
    'Options',
    'Overwrite',
    'Scale',
    'Scene',
    'Select',
    'RemoveTracks'
    'Source',
    'Stash',
    'Move Up',
    'Move Down',
    'Unassigned',
    'Prefix',
    'Suffix',
    'Timeline Markers',
    'Pose Markers',
    'Actions'
}

# Remove any strings that are in the exclude_strings set.
strings = set(filter(lambda x: x not in exclude_strings, strings))

with open('./artifacts/io_scene_psk_psa.en.po', 'w') as f:
    # Write the header (language, mime-version, content-type & content-transfer-encoding).
    f.write('msgid ""\n'
            'msgstr ""\n'
            '"Language: en\\n"\n'
            '"MIME-Version: 1.0\\n"\n'
            '"Content-Type: text/plain\\n"\n'
            '"Content-Transfer-Encoding: 8bit; charset=UTF-8\\n"\n\n'
            )
    for string in strings:
        if is_multi_line := '\n' in string:
            f.write(f'msgid ""\n')
            # Split the string into lines and write each line as a separate msgid.
            for line in string.split('\n'):
                f.write(f'"{line}"\n')
            f.write(f'msgstr ""\n')
            # Split the string into lines and write each line as a separate msgid.
            for line in string.split('\n'):
                f.write(f'"{line}"\n')
        else:
            f.write(f'msgid "{string}"\n')
            f.write(f'msgstr "{string}"\n')
        f.write('\n')

# Print the # of strings.
print(f'Found {len(strings)} strings.')

# Zip the file.
import zipfile

with zipfile.ZipFile('./artifacts/io_scene_psk_psa.po.zip', 'w') as z:
    z.write('./artifacts/io_scene_psk_psa.en.po')
