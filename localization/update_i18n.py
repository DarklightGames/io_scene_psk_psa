import os.path
import pprint
import re
from glob import glob

import polib

langs = {}

for file_path in glob('../extern/io_scene_psk_psa-translations/io_scene_psk_psa.*.po'):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        po = polib.pofile(content)

        # Get the language code from the file name.
        lang_code = re.match(r'io_scene_psk_psa.(\w*)\.po', os.path.basename(file_path)).group(1)

        if lang_code == 'en':
            continue

        langs[lang_code] = {('*', entry.msgid): entry.msgstr for entry in po if entry.msgid != ''}

with open('../io_scene_psk_psa/i18n.py', 'w', encoding='utf-8') as f:
    s = pprint.pformat(langs)
    f.write(f'langs = {s}')
    print(f'Language_codes = {list(langs.keys())}')
    print('Wrote i18n.py')
