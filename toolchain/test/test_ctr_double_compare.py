"""Compare IEEE bit patterns through real host/ARM helper calls; QEMU is not CTR."""
import argparse
import json
import math
from pathlib import Path
import random
import re
import subprocess
import tempfile

from test_ctr_double import START, number


def cases():
    anchors = [(1, 0, 1), (0x8000000000000001, 0, -1),
               (0, 0x8000000000000000, 0), (0x7ff0000000000001, 1, 2),
               (0xfff0000000000000, 0xffefffffffffffff, -1)]
    edges = [0, 1, 2, 0x000fffffffffffff, 0x0010000000000000,
             0x3ff0000000000000, 0x7fefffffffffffff, 0x7ff0000000000000,
             0x7ff0000000000001, 0x7ff8000000000000]
    edges += [x | (1 << 63) for x in edges]
    rng = random.Random(0x435452434d50)
    pairs = [(x, y) for x in edges for y in edges]
    pairs += [(rng.getrandbits(64), rng.getrandbits(64)) for _ in range(8192)]
    for left, right in pairs:
        x, y = number(left), number(right)
        expected = 2 if math.isnan(x) or math.isnan(y) else -1 if x < y else 1 if x > y else 0
        anchors.append((left, right, expected))
    return anchors


COMPARISON_FUNCTIONS = ('equal', 'unequal', 'less', 'lessEqual', 'greater', 'greaterEqual')


def audit_payload(payload, functions=COMPARISON_FUNCTIONS):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    for name in functions:
        # Dart emits instruction words as assembly data. -D overrides ARM's $d
        # mapping symbols; -d can report .word and silently miss VFP operations.
        text = subprocess.check_output([
            profile['compiler_prefix'] + 'objdump', '-D', '--disassemble=' + name,
            str(payload)], text=True)
        if '<' + name + '>:' not in text:
            raise AssertionError('missing comparison function: ' + name)
        mnemonics = re.findall(r'^\s*[0-9a-f]+:\s+[0-9a-f]+\s+(\S+)', text, re.M)
        if not mnemonics or any(op.startswith('.') for op in mnemonics):
            raise AssertionError('comparison instructions were not decoded: ' + name)
        for op in mnemonics:
            if ((op.startswith('v') and not op.startswith(('vmov', 'vldr', 'vstr', 'vpush', 'vpop'))) or
                    op.startswith(('sdiv', 'udiv', 'movw', 'movt', 'dmb', 'dsb', 'isb'))):
                raise AssertionError(f'unassisted/unsupported instruction: {name}: {op}')
    print(f'PASS {len(functions)} generated numeric functions: decoded ARM, transport-only VFP')


def run(source, native=False, baseline=False):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    data = cases()
    with tempfile.TemporaryDirectory(prefix='ctr-compare-') as directory:
        temp = Path(directory)
        (temp / 'compare_cases.h').write_text(
            'struct Case { uint64_t left, right; int expected; };\n'
            'static const Case cases[] = {\n' + ''.join(
                '{0x%016xULL,0x%016xULL,%d},\n' % row for row in data) + '};\n')
        flags = ['-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-fno-exceptions', '-fno-rtti', '-fno-builtin',
                 '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                 '-I' + str(temp), '-I' + str(source / 'runtime')]
        inputs = [str(Path(__file__).with_name('ctr_double_compare_test.cc'))]
        if baseline:
            flags.append('-DCTR_DOUBLE_BASELINE')
        else:
            inputs.append(str(source / 'runtime/vm/ctr_double_helpers.cc'))
        if native:
            before = '''  vmov r0, r1, d0
  cmp r0, #0
  bne 2f
  cmp r1, #0x00080000
  bne 2f'''
            assert START.count(before) == 1
            (temp / 'start.S').write_text(START.replace(before, '  cmn r0, #1\n  bne 2f'))
            flags += [*profile['cflags'], '-D__3DS__', '-DCTR_DOUBLE_FREESTANDING',
                      '-nostdlib', '-static', '-Wl,-e,_start', '-Wl,--build-id=none']
            inputs += [str(temp / 'start.S'), '-lgcc']
            compiler = profile['compiler_prefix'] + 'g++'
        else:
            compiler = 'g++'
        binary = temp / 'compare-test'
        subprocess.run([compiler, *flags, *inputs, '-o', str(binary)], check=True)
        if native and not baseline:
            disassembly = subprocess.check_output([
                profile['compiler_prefix'] + 'objdump', '-d', str(binary)], text=True)
            assert '<CtrDoubleCompare>:' in disassembly
            for block in re.split(r'\n(?=[0-9a-f]+ <)', disassembly):
                title = block.splitlines()[0] if block else ''
                for mnemonic in re.findall(r'^\s*[0-9a-f]+:\s+[0-9a-f]+\s+(\S+)', block, re.M):
                    transport = mnemonic.startswith(('vmov', 'vldr', 'vstr', 'vpush', 'vpop'))
                    control = ('<main>' in title or '<_start>' in title) and mnemonic in ('vmrs', 'vmsr')
                    if ((mnemonic.startswith('v') and not transport and not control) or
                            mnemonic.startswith(('sdiv', 'udiv', 'movw', 'movt', 'dmb', 'dsb', 'isb'))):
                        raise AssertionError(f'unassisted/unsupported instruction: {title}: {mnemonic}')
        command = ['qemu-arm', '-cpu', 'arm11mpcore', str(binary)] if native else [str(binary)]
        subprocess.run(command, check=True, timeout=30)
        print(f'PASS {len(data)} dynamic comparison cases: ' + ('ARM11 FZ/DN and ABI (not CTR)' if native else 'host'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--payload', type=Path, help='also audit a generated numeric AOT object')
    parser.add_argument('--payload-functions', nargs='+', default=COMPARISON_FUNCTIONS,
                        help='generated symbols to audit (defaults to the six comparisons)')
    args = parser.parse_args()
    run(args.source, args.native, args.baseline)
    if args.payload:
        audit_payload(args.payload, args.payload_functions)
