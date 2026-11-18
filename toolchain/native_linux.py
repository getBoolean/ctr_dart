#!/usr/bin/env python3
"""Check the pinned native Linux toolchain and attribute its selected providers."""
import argparse
import json
from pathlib import Path
import platform
import shutil
import sys

from common import DEFAULT_MANIFEST, DEFAULT_PROFILE, command, file_hash, read_json
from soft_math import SOFT_LIBM_SHA256, provider_path

# The provider used to qualify the software-double bridges; a version string
# alone cannot establish that the hard-float multilib is the same input.
LIBGCC_SHA256 = '1ac3ae3a4f741f6af64c8576bc420de8ae8977141b9c8594699275fbe4aefed6'


def check(manifest_path, profile_path):
    if sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise RuntimeError('native builds require Linux x86_64; on Windows use Ubuntu WSL')
    manifest, profile = read_json(manifest_path), read_json(profile_path)
    pins = manifest['container']  # Existing version pins; no image is executed.
    compiler = Path(profile['compiler_prefix'] + 'g++')
    if not compiler.is_file():
        raise RuntimeError(f'missing pinned compiler: {compiler}; install devkitARM '
                           f"{pins['devkitARM']} from the official devkitPro packages")
    version = command([compiler, '-dumpfullversion'])
    if version != pins['gcc']:
        raise RuntimeError(f"GCC version mismatch: expected {pins['gcc']}, got {version}")
    pacman = shutil.which('dkp-pacman')
    if not pacman:
        raise RuntimeError('dkp-pacman is required to attribute the official installed packages')
    packages = dict(line.split() for line in command([pacman, '-Q']).splitlines())
    for name in ('devkitARM', 'libctru'):
        if packages.get(name) != pins[name]:
            raise RuntimeError(f"{name} package mismatch: expected {pins[name]}, "
                               f"got {packages.get(name, 'not installed')}")
    providers = {}
    for name in ('libgcc.a', 'libstdc++.a', 'libc.a', 'libm.a'):
        path = Path(command([compiler, *profile['cflags'], '-print-file-name=' + name]))
        if not path.is_file():
            raise RuntimeError(f'missing selected provider: {name}: {path}')
        providers[name] = {'path': str(path.resolve()), 'sha256': file_hash(path)}
    if providers['libgcc.a']['sha256'] != LIBGCC_SHA256:
        raise RuntimeError('selected libgcc.a does not match the qualified software-double provider: '
                           + providers['libgcc.a']['sha256'])
    libctru = Path(profile['libctru']) / 'lib' / 'libctru.a'
    providers['libctru.a'] = {'path': str(libctru), 'sha256': file_hash(libctru)}
    providers['soft_libm.a'] = {'path': str(provider_path(profile)), 'sha256': SOFT_LIBM_SHA256}
    return {'scope': 'native-linux-toolchain-check-only',
            'host': {'system': platform.system(), 'release': platform.release(),
                     'machine': platform.machine(), 'python': platform.python_version(),
                     'os_release': Path('/etc/os-release').read_text()},
            'compiler': {'path': str(compiler), 'version': command([compiler, '--version']),
                         'sha256': file_hash(compiler)},
            'packages': {name: version for name, version in packages.items()
                         if name.startswith('devkitarm-') or name in
                         ('devkitARM', 'libctru', 'general-tools', '3dstools')},
            'providers': providers, 'cflags': profile['cflags'],
            'manifest_sha256': file_hash(manifest_path),
            'profile_sha256': file_hash(profile_path),
            'container_executed': Path('/.dockerenv').is_file(),
            'container_detection': 'dockerenv-marker'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check',))
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--profile', type=Path, default=DEFAULT_PROFILE)
    args = parser.parse_args()
    evidence = check(args.manifest, args.profile)
    print(json.dumps(evidence, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
