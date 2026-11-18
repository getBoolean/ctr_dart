"""Recover two known hidden files omitted by earlier Actions artifact uploads.

Donors are original bytes retained from the same SDK/repository revisions. Every
copy must match the producer's recorded digest; binaries are never substituted.
"""
import hashlib
from pathlib import Path

from bundle_native_sdk import ROOT, checked, digest, read

DATA = ROOT / 'release/transport-data'


def restore_file(destination, donor, expected):
    destination, donor = Path(destination), Path(donor)
    if destination.exists():
        if digest(destination) != expected:
            raise ValueError(f'existing component file hash mismatch: {destination}')
        return False
    content = donor.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(f'transport donor hash mismatch: {donor}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as stream:
        stream.write(content)
    return True


def restore_components(precompiler, binutils):
    precompiler, binutils = Path(precompiler), Path(binutils)
    host = read(precompiler / 'native-precompiler.json')
    name = 'bin/resources/devtools/.last_build_id'
    restored = []
    if name in host['host_dart'] and restore_file(
            precompiler / 'host-dart' / name, DATA / 'devtools-build-id.txt',
            host['host_dart'][name]['sha256']):
        restored.append('host-dart/' + name)
    sums = {}
    for line in (binutils / 'SHA256SUMS').read_text().splitlines():
        sha, name = line.split('  ', 1)
        if name in sums:
            raise ValueError('duplicate component checksum path')
        sums[name] = sha
    name = 'source/build-material/.github/workflows/native-binutils.yml'
    recipe = ('native-binutils-workflow-windows.yml'
              if sums[name] == '35d63754e009f660ef1f1e560ed78fb3732cefd64c37cea816d4fd95f9c0aa3c'
              else 'native-binutils-workflow.yml')
    if restore_file(binutils / name, DATA / recipe, sums[name]):
        restored.append(name)
    for name, sha in sums.items():
        checked(binutils, name, sha)
    return restored
