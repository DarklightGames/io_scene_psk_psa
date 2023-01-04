import re
from typing import Optional


class UReference:
    type_name: str
    package_name: str
    group_name: Optional[str]
    object_name: str

    def __init__(self, type_name: str, package_name: str, object_name: str, group_name: Optional[str] = None):
        self.type_name = type_name
        self.package_name = package_name
        self.object_name = object_name
        self.group_name = group_name

    @staticmethod
    def from_string(string: str) -> Optional['UReference']:
        if string == 'None':
            return None
        pattern = r'(\w+)\'([\w\.\d\-\_]+)\''
        match = re.match(pattern, string)
        if match is None:
            print(f'BAD REFERENCE STRING: {string}')
            return None
        type_name = match.group(1)
        object_name = match.group(2)
        pattern = r'([\w\d\-\_]+)'
        values = re.findall(pattern, object_name)
        package_name = values[0]
        object_name = values[-1]
        return UReference(type_name, package_name, object_name, group_name=None)

    def __repr__(self):
        s = f'{self.type_name}\'{self.package_name}'
        if self.group_name:
            s += f'.{self.group_name}'
        s += f'.{self.object_name}'
        return s
