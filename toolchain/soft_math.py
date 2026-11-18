"""Produce a closed software-math component with a hard-float public ABI."""
import json
from pathlib import Path
import re
import subprocess

from common import HERE, file_hash

SOFT_LIBM_SHA256 = '13fa56c130491adf4c64d5c358c64167dd174f68c87eb6b68ed7817f73898710'
BRIDGE = HERE / 'soft_math_bridge.cc'
EXPORTS = {'CtrLibm' + name for name in (
    'Pow', 'Atan2', 'Sin', 'Cos', 'Tan', 'Asin', 'Acos', 'Atan', 'Exp', 'Log',
    'Floor', 'Ceil', 'Trunc', 'Round')}
IMPORTS = {'__aeabi_' + name for name in (
    'd2f', 'd2iz', 'd2lz', 'dadd', 'dcmpeq', 'dcmpge', 'dcmpgt', 'dcmple',
    'dcmplt', 'dcmpun', 'ddiv', 'dmul', 'dsub', 'f2d', 'f2iz', 'f2lz', 'fadd',
    'fcmpeq', 'fcmpge', 'fcmpgt', 'fcmple', 'fcmplt', 'fcmpun', 'fdiv', 'fmul',
    'fsub', 'i2d', 'i2f', 'l2d', 'ui2d', 'ui2f')}
IMPORTS |= {'__errno', '__getreent', '__muldc3', '__mulsc3'}


def _run(args, capture=False):
    result = subprocess.run(list(map(str, args)), check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout if capture else None


def provider_path(profile):
    path = Path(_run([profile['compiler_prefix'] + 'g++', '-marm', '-march=armv6k',
                      '-mfloat-abi=soft', '-print-file-name=libm.a'], capture=True).strip())
    if not path.is_file() or file_hash(path) != SOFT_LIBM_SHA256:
        raise RuntimeError('software math provider hash differs from the qualified archive')
    return path.resolve()


def validate_component(path, profile, run=None):
    run = run or _run
    prefix = profile['compiler_prefix']
    symbols = run([prefix + 'nm', '-g', '--defined-only', '--format=posix', path], capture=True)
    exports = {line.split()[0] for line in symbols.splitlines() if line.split()}
    if exports != EXPORTS:
        raise RuntimeError('software math component exports differ: ' + str(sorted(exports)))
    text = run([prefix + 'nm', '-u', path], capture=True)
    imports = {line.split()[-1] for line in text.splitlines() if line.split()}
    if not imports.issubset(IMPORTS):
        raise RuntimeError('unexpected software math imports: ' + str(sorted(imports - IMPORTS)))
    header = run([prefix + 'readelf', '-h', path], capture=True)
    attributes = run([prefix + 'readelf', '-A', path], capture=True)
    if ('ELF32' not in header or 'little endian' not in header or
            not re.search(r'Machine:\s+ARM\s*$', header, re.M) or
            'Tag_ABI_VFP_args: VFP registers' not in attributes):
        raise RuntimeError('software math component lacks the CTR hard-float ELF interface')
    text = run([prefix + 'objdump', '-d', path], capture=True)
    vfp = set()
    for op, operands in re.findall(r'^\s*[0-9a-f]+:\s+[0-9a-f]+\s+(\S+)([^\n]*)', text, re.M):
        if op.startswith('v'):
            vfp.add(op)
            if (not op.startswith(('vmov', 'vldr', 'vstr', 'vpush', 'vpop')) or
                    re.search(r'\bd(?:1[6-9]|2[0-9]|3[01])\b', operands)):
                raise RuntimeError('unassisted/unsupported math instruction: ' + op + operands)
        if op.startswith(('sdiv', 'udiv', 'movw', 'movt', 'dmb', 'dsb', 'isb',
                          'ubfx', 'sbfx', 'bfi', 'bfc', 'rbit')):
            raise RuntimeError('unsupported math instruction: ' + op)
    return {'exports': sorted(exports), 'imports': sorted(imports), 'vfp': sorted(vfp),
            'attributes': attributes}


def prepare(output, profile, provider, run=None):
    run = run or _run
    if (profile.get('arm_float_abi') != 'hard' or
            not {'-marm', '-march=armv6k', '-mfloat-abi=hard'}.issubset(profile['cflags'])):
        raise RuntimeError('software math requires the CTR hard-float public profile')
    provider, output = Path(provider).resolve(), Path(output)
    if not provider.is_file() or file_hash(provider) != SOFT_LIBM_SHA256:
        raise RuntimeError('software math provider hash differs from the qualified archive')
    hashes = {'provider': SOFT_LIBM_SHA256, 'bridge': file_hash(BRIDGE),
              'producer': file_hash(__file__)}
    output.mkdir(parents=True, exist_ok=False)
    prefix = profile['compiler_prefix']
    text = run([prefix + 'nm', '-g', '--defined-only', '--format=posix', provider], capture=True)
    names = sorted({line.split()[0] for line in text.splitlines()
                    if len(line.split()) >= 3 and len(line.split()[1]) == 1})
    if len(names) != 383 or not {'__ieee754_pow', 'sin', '__ieee754_log'}.issubset(names):
        raise RuntimeError('unexpected software math archive symbol inventory')
    mapping, local = output / 'rename.txt', output / 'localize.txt'
    mapping.write_text(''.join(f'{name} ctr_soft_{name}\n' for name in names))
    local.write_text(''.join(f'ctr_soft_{name}\n' for name in names))
    archive, bridge = output / 'private.a', output / 'bridge.o'
    run([prefix + 'objcopy', '-D', '--redefine-syms=' + str(mapping), provider, archive])
    run([prefix + 'g++', '-std=c++20', '-O2', '-fno-builtin', '-fno-exceptions',
         '-fno-rtti', '-ffunction-sections', '-fdata-sections', *profile['cflags'],
         '-c', BRIDGE, '-o', bridge])
    combined, component = output / 'combined.o', output / 'component.o'
    # Only this pinned private component mixes PCS variants. Localizing every
    # base-PCS definition leaves a hard-float public interface; final executable
    # links never inherit this coarse partial-link exception.
    run([prefix + 'ld', '-r', '--no-warn-mismatch', '-o', combined, bridge,
         '--whole-archive', archive, '--no-whole-archive'])
    run([prefix + 'objcopy', '--localize-symbols=' + str(local), combined, component])
    audit = validate_component(component, profile, run)
    if (file_hash(provider) != hashes['provider'] or file_hash(BRIDGE) != hashes['bridge'] or
            file_hash(__file__) != hashes['producer']):
        raise RuntimeError('software math input changed while producing the component')
    record = {'schema': 1, 'inputs': hashes, 'object_sha256': file_hash(component),
              'exports': audit['exports'], 'audit': audit,
              'partial_link_exception': 'pinned private base-PCS archive and hard-float adapters only',
              'final_link_mismatch_check': 'enabled'}
    (output / 'component.json').write_text(json.dumps(record, indent=2) + '\n')
    return component, record
