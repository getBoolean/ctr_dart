"""Shared identity and checked subprocess operations for the CTR SDK tools."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_MANIFEST = HERE / 'versions.json'
DEFAULT_PROFILE = HERE / 'target-ctr.json'
DEFAULT_SOURCE = ROOT / 'third_party' / 'dart-sdk'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, cwd=None, env=None, capture=True):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(map(str, args))}\n"
                           f"{result.stderr or ''}")
    return result.stdout.strip() if capture else ''


def git(source, *args, env=None):
    return command(['git', '-c', 'core.autocrlf=false', '-c', 'core.safecrlf=false',
                    '-c', 'core.hooksPath=', '-C', source, *args], env=env)


def patch_inputs(manifest_path, entries):
    manifest_path = Path(manifest_path).resolve()
    patches = []
    for patch in entries:
        path = (manifest_path.parent / patch['path']).resolve()
        actual = file_hash(path)
        if actual != patch['sha256']:
            raise RuntimeError(f"patch hash mismatch: {path}; expected {patch['sha256']}, got {actual}")
        patches.append((path, patch))
    return patches


def source_inputs(manifest_path):
    manifest = read_json(manifest_path)
    patches = patch_inputs(manifest_path, manifest['patches'])
    if 'icu' in manifest.get('dependencies', {}):
        patch_inputs(manifest_path, manifest['dependencies']['icu']['patches'])
    return manifest, patches


def verify_icu(source, manifest):
    pin = manifest.get('dependencies', {}).get('icu')
    if pin:
        return verify_source(Path(source) / 'third_party' / 'icu',
                             {'dart': pin, 'patches': pin['patches']})


def source_identity(manifest):
    return {'repository': manifest['dart']['repository'],
            'upstream_revision': manifest['dart']['revision'],
            'patches': manifest['patches']}


def verify_source(source, manifest):
    source = Path(source)
    state_path = source / '.git' / 'ctr-source.json'
    if not state_path.is_file():
        raise RuntimeError(f"unmanaged source directory: {source}; choose an absent directory")
    if git(source, 'status', '--porcelain', '--untracked-files=all'):
        raise RuntimeError(f"dirty source checkout: {source}; preserve/export edits before retrying")
    state = read_json(state_path)
    if state['inputs'] != source_identity(manifest) or git(source, 'rev-parse', 'HEAD') != state['head']:
        raise RuntimeError(f"source checkout mismatch: {source}; choose a new source directory")
    return state


def build_identity(manifest_path, profile_path, component, mode):
    manifest, _ = source_inputs(manifest_path)
    profile = read_json(profile_path)
    gn_args = {'target_os': 'linux', 'target_cpu': 'x64', 'is_debug': False, 'is_release': True,
               'is_clang': True, 'dart_use_crashpad': False}
    root_target = '//:create_sdk'
    executable_os, executable_cpu = 'linux', 'x64'
    if component in ('target', 'precompiler', 'probe'):
        gn_args.update({key: profile[key] for key in ('target_os', 'target_cpu', 'arm_version',
                       'arm_fpu', 'arm_float_abi', 'arm_use_neon', 'arm_use_integer_division')})
        gn_args.update({'is_clang': False, 'dart_use_compressed_pointers': False,
                        'dart_target_arch': 'arm', 'dart_support_perfetto': False})
        root_target = ('//build/toolchain/ctr:' if component == 'probe' else '//build/ctr:') + {
            'precompiler': 'precompiler', 'probe': 'abi_probe',
            'target': 'aot_runtime' if mode == 'aot' else 'jit_runtime'}[component]
        if component in ('target', 'probe'):
            executable_os, executable_cpu = 'ctr', 'arm'
        if component == 'probe':
            for key in ('dart_use_crashpad', 'dart_use_compressed_pointers',
                        'dart_target_arch', 'dart_support_perfetto'):
                gn_args.pop(key, None)
    specs = [{'path': path, 'sha256': file_hash(Path(profile_path).resolve().parent / path)}
             for path in profile.get('link_specs', [])]
    # No stock SDK hash override: upstream computes it from the patched sources.
    inputs = {'manifest': manifest, 'profile': profile, 'component': component, 'mode': mode,
              'core_image': manifest.get('formats', {}).get('core_image', 'upstream'),
              'snapshot': manifest.get('formats', {}).get('snapshot', 'upstream'),
              'gn_args': gn_args, 'link_specs': specs, 'root_target': root_target}
    return {'cache_key': digest(inputs), 'component': component, 'mode': mode,
            'gn_args': gn_args, 'inputs': inputs, 'root_target': root_target,
            'executable_os': executable_os, 'executable_cpu': executable_cpu}
