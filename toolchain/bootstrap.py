#!/usr/bin/env python3
"""Materialize pinned sources without changing an existing unmanaged/dirty tree."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.request
import zipfile

from common import (DEFAULT_MANIFEST, DEFAULT_SOURCE, ROOT, command, file_hash, git,
                    patch_inputs, source_identity, source_inputs, verify_source)


def materialize(source, manifest, patches):
    source = Path(source).resolve()
    if source.exists():
        return verify_source(source, manifest)
    source.mkdir(parents=True)
    # Failure leaves the new directory for inspection. Never reset/clean caller state.
    git(source, 'init', '--quiet')
    git(source, 'remote', 'add', 'origin', manifest['dart']['repository'])
    git(source, 'fetch', '--quiet', '--depth=1', 'origin', manifest['dart']['revision'])
    git(source, 'checkout', '--quiet', '--detach', manifest['dart']['revision'])
    return apply_patches(source, manifest, patches)


def apply_patches(source, manifest, patches):
    env = os.environ.copy()
    env.update({'GIT_AUTHOR_NAME': 'CTR SDK patches', 'GIT_AUTHOR_EMAIL': 'ctr-sdk@example.invalid',
                'GIT_COMMITTER_NAME': 'CTR SDK patches', 'GIT_COMMITTER_EMAIL': 'ctr-sdk@example.invalid',
                'GIT_AUTHOR_DATE': '2000-01-01T00:00:00Z', 'GIT_COMMITTER_DATE': '2000-01-01T00:00:00Z'})
    for path, patch in patches:
        git(source, 'apply', '--check', path)
        git(source, 'apply', '--index', path)
        git(source, '-c', 'commit.gpgsign=false', 'commit', '--quiet', '--no-verify',
            '-m', f"Apply CTR patch {patch['path']}\n\nSHA256: {patch['sha256']}", env=env)
    state = {'inputs': source_identity(manifest), 'head': git(source, 'rev-parse', 'HEAD'),
             'upstream_revision': manifest['dart']['revision'], 'patches': manifest['patches']}
    (source / '.git' / 'ctr-source.json').write_text(json.dumps(state, indent=2) + '\n')
    return verify_source(source, manifest)


def patch_icu(source, manifest, manifest_path):
    pin = manifest.get('dependencies', {}).get('icu')
    if not pin:
        return
    dependency = Path(source) / 'third_party' / 'icu'
    inputs = {'dart': pin, 'patches': pin['patches']}
    patches = patch_inputs(manifest_path, pin['patches'])
    if git(dependency, 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError(f'dirty ICU checkout: {dependency}; preserve/export edits before retrying')
    if git(dependency, 'rev-parse', 'HEAD') != pin['revision']:
        return verify_source(dependency, inputs)
    return apply_patches(dependency, inputs, patches)


def sync_dependencies(source, manifest, depot, manifest_path=DEFAULT_MANIFEST):
    if sys.platform != 'linux':
        raise RuntimeError('dependency sync requires native Linux x64 or Ubuntu WSL')
    expected = manifest['dependencies']['dart_deps']['sha256']
    actual = file_hash(source / manifest['dependencies']['dart_deps']['path'])
    if actual != expected:
        raise RuntimeError(f'DEPS hash mismatch: expected {expected}, got {actual}')
    pin = manifest['dependencies']['depot_tools']
    materialize(depot, {'dart': pin, 'patches': []}, [])
    config = ('solutions = ' + repr([{'name': source.name, 'url': manifest['dart']['repository'],
               'managed': False, 'custom_deps': {}, 'custom_vars': {
                   **manifest['dependencies']['gclient_variables'], 'dart_root': source.name}}]) + '\n')
    config_path = source.parent / '.gclient'
    if config_path.exists() and config_path.read_text() != config:
        raise RuntimeError(f'unmanaged or mismatched gclient configuration: {config_path}')
    config_path.write_text(config)
    env = os.environ.copy()
    env.update({'PATH': str(depot) + os.pathsep + env['PATH'], 'DEPOT_TOOLS_UPDATE': '0',
                'DEPOT_TOOLS_METRICS': '0'})
    command([depot / 'gclient', 'sync', '--no-history', '--shallow', '--nohooks'],
            cwd=source.parent, env=env, capture=False)
    command([depot / 'gclient', 'runhooks'], cwd=source.parent, env=env, capture=False)
    patch_icu(source, manifest, manifest_path)
    verify_source(source, manifest)


def fetch_gn(source, manifest):
    pin = manifest['dependencies']['gn']
    destination = source / 'buildtools' / 'gn'
    if destination.exists():
        if file_hash(destination) != pin['binary_sha256']:
            raise RuntimeError(f'existing GN hash mismatch: {destination}')
        return
    url = 'https://chrome-infra-packages.appspot.com/dl/' + pin['package'] + '/+/' + pin['revision']
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'gn.zip'
        urllib.request.urlretrieve(url, archive)
        if file_hash(archive) != pin['archive_sha256']:
            raise RuntimeError('downloaded GN archive hash mismatch')
        with zipfile.ZipFile(archive) as package:
            data = package.read('gn')
        import hashlib
        if hashlib.sha256(data).hexdigest() != pin['binary_sha256']:
            raise RuntimeError('downloaded GN binary hash mismatch')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--sync-deps', action='store_true')
    parser.add_argument('--fetch-gn', action='store_true',
                        help='fetch only the pinned Linux GN package for the native ABI configuration')
    parser.add_argument('--depot-tools', type=Path, default=ROOT / 'third_party' / 'depot_tools')
    args = parser.parse_args()
    manifest, patches = source_inputs(args.manifest)
    state = materialize(args.source, manifest, patches)
    if args.fetch_gn:
        fetch_gn(args.source.resolve(), manifest)
    if args.sync_deps:
        sync_dependencies(args.source.resolve(), manifest, args.depot_tools.resolve(), args.manifest)
    print(json.dumps(state, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
