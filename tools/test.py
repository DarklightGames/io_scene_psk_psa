"""
Runs the test suite against one or more supported Blender versions (see `pyproject.toml`).

The newest version is tested in the project's default environment (`.venv/`).
Other versions are each tested in their own environment under `.venvs/`, using
the `bpy` module and Python version locked for them in `uv.lock`.

Usage:
    uv run test                  # Test the newest supported version.
    uv run test 5.0 5.2          # Test specific versions.
    uv run test all              # Test all supported versions.
    uv run test 5.0 -- -k psa    # Pass extra arguments to pytest.
"""
import argparse
import os
import subprocess
import sys
import time

from tools.blender_versions import (
    REPOSITORY_ROOT,
    BlenderVersion,
    find_blender_version,
    get_supported_blender_versions,
)


def run_tests(version: BlenderVersion, is_default: bool, pytest_args: list[str]) -> bool:
    environment = dict(os.environ)
    if not is_default:
        environment['UV_PROJECT_ENVIRONMENT'] = str(REPOSITORY_ROOT / '.venvs' / version.group)
    # Lets the test suite verify that it is running against the intended version.
    environment['EXPECTED_BLENDER_VERSION'] = version.name
    environment.pop('VIRTUAL_ENV', None)
    command = [
        'uv', 'run', '--locked',
        '--python', version.python,
        '--no-default-groups', '--group', 'dev', '--group', version.group,
        'pytest', *pytest_args,
    ]
    print(f'\n=== Blender {version.name} (Python {version.python}) ===', flush=True)
    return subprocess.run(command, cwd=REPOSITORY_ROOT, env=environment).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog='uv run test',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Arguments after `--` are passed to pytest.',
    )
    parser.add_argument(
        'versions', nargs='*', metavar='VERSION',
        help='Blender versions to test, or `all` (default: the newest supported version).',
    )
    argv = sys.argv[1:]
    if '--' in argv:
        argv, pytest_args = argv[:argv.index('--')], argv[argv.index('--') + 1:]
    else:
        pytest_args = []
    args = parser.parse_args(argv)

    supported_versions = get_supported_blender_versions()
    newest = supported_versions[-1]
    try:
        if 'all' in args.versions:
            versions = supported_versions
        elif args.versions:
            versions = [find_blender_version(v) for v in args.versions]
        else:
            versions = [newest]
    except ValueError as e:
        parser.error(str(e))

    results = []
    for version in versions:
        start = time.monotonic()
        passed = run_tests(version, version == newest, pytest_args)
        results.append((version, passed, time.monotonic() - start))

    if len(results) > 1:
        print('\n=== Summary ===')
        for version, passed, duration in results:
            print(f'Blender {version.name}: {"PASSED" if passed else "FAILED"} ({duration:.0f}s)')
    return 0 if all(passed for _, passed, _ in results) else 1


if __name__ == '__main__':
    sys.exit(main())
