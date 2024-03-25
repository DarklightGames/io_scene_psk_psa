import ast
import glob
import os
import pathlib

import polib

# Walk the directory and open all .py files using glob
strings = dict()
root_path = pathlib.Path('../io_scene_psk_psa').resolve()
for file in glob.glob('../io_scene_psk_psa/**/*.py', recursive=True):
    with open(os.path.join(file), 'r') as f:
        if file.endswith('i18n.py'):
            # TODO: Don't parse the i18n files.
            continue
        # Walk the entire tree and build a list of all string literals.
        try:
            a = ast.parse(f.read())
            for node in ast.walk(a):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    a = pathlib.Path(file).resolve()
                    filepath = a.relative_to(root_path)
                    if node.s not in strings:
                        strings[node.s] = filepath, node.lineno, node.col_offset
        except UnicodeDecodeError as e:
            print(f'Error reading file {file}: {e}')

string_keys = set(strings.keys())

# Remove all keys from the dictionary that are empty or contain only whitespace.
string_keys = set(filter(lambda x: x.strip(), string_keys))

# Remove all strings that have no alphabetic characters.
string_keys = set(filter(lambda x: any(c.isalpha() for c in x), string_keys))

# Remove any strings that have '@return: ' in them.
string_keys = set(filter(lambda x: '@return: ' not in x, string_keys))

# Remove any strings that are entirely lowercase and have no whitespace.
string_keys = set(filter(lambda x: not x.islower() or ' ' in x, string_keys))

# Remove any strings that are in SCREAMING_SNAKE_CASE.
string_keys = set(filter(lambda x: not x.isupper(), string_keys))

# Remove any strings that have underscores and no spaces.
string_keys = set(filter(lambda x: '_' not in x or ' ' in x, string_keys))

# Remove any string that starts with a newline.
string_keys = set(filter(lambda x: not x.startswith('\n'), string_keys))

# Remove any string that looks like a regular expression.
string_keys = set(filter(lambda x: not any(c in x for c in '^'), string_keys))

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
    'Move Up',
    'Move Down',
    'Unassigned',
    'Prefix',
    'Suffix',
    'Timeline Markers',
    'Pose Markers',
    'Actions',
    'sRGBA',
}

# Remove any strings that are in the exclude_strings set.
string_keys = set(filter(lambda x: x not in exclude_strings, string_keys))

# Make a new PO file and write the strings to it.
pofile = polib.POFile()

pofile.header = '''msgid ""
msgstr ""
"Language: en\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
'''

# Sort the string keys into a list.
string_keys = list(string_keys)
string_keys.sort()

for string_key in string_keys:
    file, line, col = strings[string_key]
    entry = polib.POEntry(
        msgid=string_key,
        msgstr=string_key,
        comment=f'{file}:{line}',
    )
    pofile.append(entry)

pofile.save('../extern/io_scene_psk_psa-translations/io_scene_psk_psa.en.po')

# Print the # of strings.
print(f'Found {len(string_keys)} strings.')
