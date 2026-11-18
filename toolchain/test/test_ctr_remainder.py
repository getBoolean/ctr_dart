"""Check truncating remainder and Dart's rounded modulo adjustment independently."""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import random
import re
import subprocess
import tempfile

from test_ctr_double import START, bits, number


def oracle(left, right):
    x, y = number(left), number(right)
    if not math.isfinite(x) or math.isnan(y) or y == 0:
        remainder = math.nan
    elif math.isinf(y):
        remainder = x
    else:
        exact = abs(Fraction(x)) % abs(Fraction(y))
        remainder = math.copysign(float(exact), x)
        assert abs(Fraction(remainder)) == exact  # Remainder is exactly representable.
        assert bits(remainder) == bits(math.fmod(x, y))
    # Match the pinned VM: one binary64 addition, which can round to |y|.
    modulo = (0.0 if remainder == 0 else
              remainder + abs(y) if remainder < 0 else remainder)
    nan = 0x7ff8000000000000
    return (nan if math.isnan(remainder) else bits(remainder),
            nan if math.isnan(modulo) else bits(modulo))


def cases():
    sign = 1 << 63
    pairs = [(7, 3), (sign | 7, 3), (sign, 3),
             (0x0010000000000000, 0x000fffffffffffff)]
    edges = [0, 1, 2, 3, 7, 0x000fffffffffffff, 0x0010000000000000,
             bits(0.5), bits(1), bits(2), bits(3), 0x7fefffffffffffff,
             0x7ff0000000000000, 0x7ff0000000000001, 0x7ff8000000000001]
    edges += [value | sign for value in edges]
    pairs += [(x, y) for x in edges for y in edges]
    pairs += [(x | sx, y | sy) for x in range(1, 66) for y in range(1, 18)
              for sx in (0, sign) for sy in (0, sign)]
    for exponent in range(2047):
        x = (exponent << 52) | 0x000aaaaaaaaaaaaa
        pairs += [(x, 3), (x | sign, 0x0010000000000001)]
    rng = random.Random(0x43545252454d)
    pairs += [(rng.getrandbits(64), rng.getrandbits(64)) for _ in range(4096)]
    return [(x, y, *oracle(x, y)) for x, y in pairs]


def run(source, native):
    rows = cases()
    projected = rows[:34] + rows[34::31]
    observed = [tuple(int(value, 16) for value in row) for row in re.findall(
        r'\[(0x[0-9a-f]+),(0x[0-9a-f]+),(0x[0-9a-f]+),(0x[0-9a-f]+)\]',
        (source / 'runtime/ctr/test/numeric_remainder_cases.dart').read_text())]
    if observed != projected:
        raise AssertionError('Dart remainder goldens differ from the exact rational oracle')
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    with tempfile.TemporaryDirectory(prefix='ctr-remainder-') as directory:
        temp = Path(directory)
        (temp / 'remainder_cases.h').write_text(
            'struct Case { uint64_t left, right, remainder, modulo; };\n'
            'static const Case cases[] = {\n' + ''.join(
                '{0x%016xULL,0x%016xULL,0x%016xULL,0x%016xULL},\n' % row
                for row in rows) + '};\n')
        flags = ['-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-fno-exceptions',
                 '-fno-rtti', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
                 '-Wl,--gc-sections', '-I' + str(temp), '-I' + str(source / 'runtime')]
        inputs = [str(Path(__file__).with_name('ctr_remainder_test.cc')),
                  str(source / 'runtime/vm/ctr_double_helpers.cc')]
        compiler = 'g++'
        if native:
            before = '''  cmp r0, #0
  bne 2f
  cmp r1, #0x00080000'''
            assert START.count(before) == 1
            (temp / 'start.S').write_text(START.replace(before, '''  cmp r0, #1
  bne 2f
  cmp r1, #0'''))
            flags += [*profile['cflags'], '-D__3DS__', '-DCTR_REMAINDER_FREESTANDING',
                      '-nostdlib', '-static', '-Wl,-e,_start', '-Wl,--build-id=none']
            inputs += [str(temp / 'start.S'), '-lgcc']
            compiler = profile['compiler_prefix'] + 'g++'
        binary = temp / 'remainder-test'
        subprocess.run([compiler, *flags, *inputs, '-o', str(binary)], check=True)
        if native:
            disassembly = subprocess.check_output([
                profile['compiler_prefix'] + 'objdump', '-d', str(binary)], text=True)
            assert '<CtrDoubleRemainder>:' in disassembly and '<CtrDoubleModulo>:' in disassembly
            for block in re.split(r'\n(?=[0-9a-f]+ <)', disassembly):
                title = block.splitlines()[0] if block else ''
                for op in re.findall(r'^\s*[0-9a-f]+:\s+[0-9a-f]+\s+(\S+)', block, re.M):
                    transport = op.startswith(('vmov', 'vldr', 'vstr', 'vpush', 'vpop'))
                    control = ('<main>' in title or '<_start>' in title) and op in ('vmrs', 'vmsr')
                    if ((op.startswith('v') and not transport and not control) or
                            op.startswith(('sdiv', 'udiv', 'movw', 'movt', 'dmb', 'dsb', 'isb'))):
                        raise AssertionError(f'unassisted/unsupported instruction: {title}: {op}')
        command = ['qemu-arm', '-cpu', 'arm11mpcore', str(binary)] if native else [str(binary)]
        subprocess.run(command, check=True, timeout=60)
        print(f'PASS {len(rows)} remainder/modulo pairs: ' + ('ARM11 FZ/DN and ABI (not CTR)' if native else 'host'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args()
    run(args.source, args.native)
