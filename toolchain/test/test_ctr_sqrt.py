"""Check dynamic square roots and exact rounding certificates; QEMU is not CTR."""
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


def certify(input_bits, expected_bits):
    value = number(input_bits)
    if value <= 0 or not math.isfinite(value):
        return
    root = Fraction.from_float(number(expected_bits))
    lower = (root + Fraction.from_float(number(expected_bits - 1))) / 2
    upper = (root + Fraction.from_float(number(expected_bits + 1))) / 2
    exact = Fraction.from_float(value)
    assert lower * lower <= exact <= upper * upper
    if exact in (lower * lower, upper * upper):
        assert expected_bits % 2 == 0


def cases():
    edges = [0, 1, 2, 3, 0x000fffffffffffff, 0x0010000000000000,
             bits(1), bits(2), bits(4), 0x7fefffffffffffff,
             0x7ff0000000000000, 0x7ff0000000000001, 0x7ff8000000000001]
    inputs = edges + [value | (1 << 63) for value in edges]
    for exponent in range(2047):
        inputs += [(exponent << 52) | fraction for fraction in
                   (0, 1, 2, 0x0007ffffffffffff, 0x000ffffffffffffe, 0x000fffffffffffff)]
    for root in (1, 2, 3, 7, 2**26 - 1, 2**26 + 1, 2**27 - 1, 2**27 + 1,
                 2**52 - 1, 2**52 + 1, 2**53 - 1):
        square = float(root * root)
        inputs += [bits(math.nextafter(square, direction)) for direction in (0, math.inf)]
        inputs.append(bits(square))
    rng = random.Random(0x43545253515254)
    inputs += [rng.getrandbits(64) for _ in range(16384)]
    result = []
    for index, pattern in enumerate(inputs):
        value = number(pattern)
        root = math.nan if value < 0 else math.sqrt(value)
        expected = 0x7ff8000000000000 if math.isnan(root) else bits(root)
        if index < 26 or index % 47 == 0:
            certify(pattern, expected)
        result.append((pattern, expected))
    assert result[1] == (1, 0x1e60000000000000)
    return result


def run(source, native=False, baseline=False):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    rows = cases()
    expected = rows[:26] + rows[26::47]
    observed = [tuple(int(value, 16) for value in row) for row in re.findall(
        r'\[(0x[0-9a-f]+),(0x[0-9a-f]+)\]',
        (source / 'runtime/ctr/test/numeric_sqrt_cases.dart').read_text())]
    if observed != expected:
        raise AssertionError('Dart sqrt goldens differ from the certified host oracle')
    with tempfile.TemporaryDirectory(prefix='ctr-sqrt-') as directory:
        temp = Path(directory)
        (temp / 'sqrt_cases.h').write_text(
            'struct Case { uint64_t input, expected; };\nstatic const Case cases[] = {\n' +
            ''.join('{0x%016xULL,0x%016xULL},\n' % row for row in rows) + '};\n')
        flags = ['-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-fno-exceptions',
                 '-fno-rtti', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
                 '-Wl,--gc-sections', '-I' + str(temp), '-I' + str(source / 'runtime')]
        inputs = [str(Path(__file__).with_name('ctr_sqrt_test.cc'))]
        if baseline:
            flags.append('-DCTR_SQRT_BASELINE')
        else:
            inputs.append(str(source / 'runtime/vm/ctr_double_helpers.cc'))
        if native:
            assert START.count('cmp r1, #0x00080000') == 1
            (temp / 'start.S').write_text(START.replace('cmp r1, #0x00080000', 'cmp r1, #0x20000000'))
            flags += [*profile['cflags'], '-D__3DS__', '-DCTR_SQRT_FREESTANDING',
                      '-nostdlib', '-static', '-Wl,-e,_start', '-Wl,--build-id=none']
            inputs += [str(temp / 'start.S'), '-lgcc']
            compiler = profile['compiler_prefix'] + 'g++'
        else:
            compiler = 'g++'
        binary = temp / 'sqrt-test'
        subprocess.run([compiler, *flags, *inputs, '-o', str(binary)], check=True)
        if native and not baseline:
            disassembly = subprocess.check_output([
                profile['compiler_prefix'] + 'objdump', '-d', str(binary)], text=True)
            assert '<CtrDoubleSqrt>:' in disassembly
            for block in re.split(r'\n(?=[0-9a-f]+ <)', disassembly):
                title = block.splitlines()[0] if block else ''
                for op in re.findall(r'^\s*[0-9a-f]+:\s+[0-9a-f]+\s+(\S+)', block, re.M):
                    transport = op.startswith(('vmov', 'vldr', 'vstr', 'vpush', 'vpop'))
                    control = ('<main>' in title or '<_start>' in title) and op in ('vmrs', 'vmsr')
                    if ((op.startswith('v') and not transport and not control) or
                            op.startswith(('sdiv', 'udiv', 'movw', 'movt', 'dmb', 'dsb', 'isb'))):
                        raise AssertionError(f'unassisted/unsupported instruction: {title}: {op}')
        command = ['qemu-arm', '-cpu', 'arm11mpcore', str(binary)] if native else [str(binary)]
        subprocess.run(command, check=True, timeout=30)
        print(f'PASS {len(rows)} dynamic square roots: ' + ('ARM11 FZ/DN and ABI (not CTR)' if native else 'host'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    run(args.source, args.native, args.baseline)
