"""
Reads the supported Blender versions from the `blender-*` dependency groups in
`pyproject.toml`. Run directly to print them as JSON (used by CI); this only
needs the standard library.
"""

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPOSITORY_ROOT / 'pyproject.toml'
MANIFEST_PATH = REPOSITORY_ROOT / 'io_scene_psk_psa' / 'blender_manifest.toml'
PYTHON_VERSION_PATH = REPOSITORY_ROOT / '.python-version'

_GROUP_PATTERN = re.compile(r'^blender-(\d+)-(\d+)$')
_REQUIREMENT_PATTERN = re.compile(r"""^bpy==(\d+)\.(\d+)\.\*\s*;\s*python_version\s*==\s*['"](\d+\.\d+)['"]$""")


@dataclass(frozen=True)
class BlenderVersion:
    major: int
    minor: int
    python: str

    @property
    def name(self) -> str:
        return f'{self.major}.{self.minor}'

    @property
    def group(self) -> str:
        return f'blender-{self.major}-{self.minor}'


def _load_pyproject() -> dict:
    with open(PYPROJECT_PATH, 'rb') as f:
        return tomllib.load(f)


def get_supported_blender_versions() -> list[BlenderVersion]:
    """Returns the supported Blender versions, sorted from oldest to newest."""
    groups = _load_pyproject().get('dependency-groups', {})
    versions = []
    for group, requirements in groups.items():
        group_match = _GROUP_PATTERN.match(group)
        if group_match is None:
            continue
        if len(requirements) != 1 or not isinstance(requirements[0], str):
            raise ValueError(f'Dependency group "{group}" must contain exactly one `bpy` requirement')
        requirement_match = _REQUIREMENT_PATTERN.match(requirements[0])
        if requirement_match is None:
            raise ValueError(
                f'Dependency group "{group}" has an unexpected requirement: {requirements[0]!r} '
                '(expected the form "bpy==X.Y.*; python_version == \'A.B\'")'
            )
        major, minor, python = requirement_match.groups()
        if (major, minor) != group_match.groups():
            raise ValueError(f'Dependency group "{group}" requires the wrong `bpy` version: {requirements[0]!r}')
        versions.append(BlenderVersion(int(major), int(minor), python))
    if not versions:
        raise ValueError(f'No `blender-*` dependency groups found in {PYPROJECT_PATH}')
    return sorted(versions, key=lambda v: (v.major, v.minor))


def find_blender_version(name: str) -> BlenderVersion:
    for version in get_supported_blender_versions():
        if version.name == name:
            return version
    supported = ', '.join(v.name for v in get_supported_blender_versions())
    raise ValueError(f'Blender {name} is not a supported version (supported: {supported})')


def check_project_configuration() -> list[str]:
    """Returns a list of problems where the project configuration disagrees with the supported versions."""
    problems = []
    versions = get_supported_blender_versions()
    oldest, newest = versions[0], versions[-1]
    uv_config = _load_pyproject().get('tool', {}).get('uv', {})

    # Every version group must be mutually exclusive, in a single conflict set.
    conflict_sets = [{item.get('group') for item in conflict_set} for conflict_set in uv_config.get('conflicts', [])]
    expected_groups = {v.group for v in versions}
    if expected_groups not in conflict_sets:
        problems.append(
            f'`[tool.uv] conflicts` must contain exactly one set with all of the Blender groups: {sorted(expected_groups)}'
        )

    # The default environment must use the newest version.
    default_blender_groups = [g for g in uv_config.get('default-groups', []) if _GROUP_PATTERN.match(g)]
    if default_blender_groups != [newest.group]:
        problems.append(
            f'`[tool.uv] default-groups` must contain "{newest.group}" (the newest version) and no other Blender group; '
            f'found {default_blender_groups}'
        )

    # The default environment's Python must be the one the newest version requires.
    python_version = PYTHON_VERSION_PATH.read_text().strip() if PYTHON_VERSION_PATH.exists() else None
    if python_version != newest.python:
        problems.append(
            f'`.python-version` must be "{newest.python}" (required by Blender {newest.name}); found {python_version!r}'
        )

    # The add-on must claim to support exactly the tested versions.
    with open(MANIFEST_PATH, 'rb') as f:
        manifest = tomllib.load(f)
    version_min = manifest.get('blender_version_min', '')
    if tuple(int(x) for x in version_min.split('.')[:2]) != (oldest.major, oldest.minor):
        problems.append(
            f'`blender_version_min` in {MANIFEST_PATH.name} must be "{oldest.name}.0" (the oldest supported version); '
            f'found "{version_min}"'
        )
    version_max = manifest.get('blender_version_max')
    if version_max is not None and tuple(int(x) for x in version_max.split('.')[:2]) <= (newest.major, newest.minor):
        problems.append(
            f'`blender_version_max` in {MANIFEST_PATH.name} ("{version_max}") excludes Blender {newest.name}, '
            'which is a supported version'
        )

    return problems


if __name__ == '__main__':
    print(json.dumps([v.name for v in get_supported_blender_versions()]))
