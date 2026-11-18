"""Qualify bounded software power shortcuts; general pow remains separate."""
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
from test_ctr_sqrt import cases as sqrt_cases


def cases():
    rows = []
    for value, expected in sqrt_cases():
        # IEEE pow(-0, 0.5) is +0; pow(-infinity, 0.5) is +infinity.
        if value == 0x8000000000000000:
            expected = 0
        elif value == 0xfff0000000000000:
            expected = 0x7ff0000000000000
        rows.append((value, bits(0.5), expected, True))
    edges = [0, 1, 0x000fffffffffffff, 0x0010000000000000,
             bits(1), bits(2), 0x7fefffffffffffff, 0x7ff0000000000000,
             0x7ff8000000000001, 0x7ff0000000000001]
    edges += [v | (1 << 63) for v in edges]
    rng = random.Random(0x435452504f57)
    inputs = edges + [rng.getrandbits(64) for _ in range(2048)]
    for value in inputs:
        for exponent in (0.0, -0.0, 1.0, 2.0):
            try:
                x = number(value)
                # The VM square shortcut has one correctly rounded product.
                # Host libm pow(x, 2) can differ by one ULP, so use an exact
                # rational product, rounded once to binary64, for finite x.
                expected = (float(Fraction(x) ** 2)
                            if exponent == 2.0 and math.isfinite(x)
                            else math.pow(x, exponent))
            except ValueError:
                expected = math.nan
            except OverflowError:
                expected = math.inf
            rows.append((value, bits(exponent), bits(expected), True))
    # Cubes preserve the VM's two sequential multiplications. Use exact powers
    # of two, including underflow/overflow boundaries, for independent goldens.
    for exponent in (-1074, -512, -359, -358, -357, -1, 0, 1, 341, 342, 1023):
        for sign in (1, -1):
            value = sign * math.ldexp(1.0, exponent)
            try:
                result = sign * math.ldexp(1.0, exponent * 3)
            except OverflowError:
                result = math.copysign(math.inf, sign)
            rows.append((bits(value), bits(3), bits(result), True))
    for exponent in edges:
        rows.append((bits(1), exponent, bits(1), True))
    for value in (bits(2), bits(-2), 1):
        for exponent in (1, bits(-1), bits(4), bits(1.25)):
            rows.append((value, exponent, 0x123456789abcdef0, False))
    return rows


def run(source, native):
    rows = cases()
    projected = [row for row in rows[:26] + rows[26::47] + rows[-54:-12] if row[3]]
    observed = [tuple(int(value, 16) for value in row) for row in re.findall(
        r'\[(0x[0-9a-f]+),(0x[0-9a-f]+),(0x[0-9a-f]+)\]',
        (source / 'runtime/ctr/test/numeric_pow_cases.dart').read_text())]
    if observed != [row[:3] for row in projected]:
        raise AssertionError('Dart power goldens differ from the independent oracle')
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    with tempfile.TemporaryDirectory(prefix='ctr-pow-') as directory:
        temp = Path(directory)
        (temp / 'pow_cases.h').write_text(
            'struct Case { uint64_t base, exponent, expected; bool handled; };\n'
            'static const Case cases[] = {\n' + ''.join(
                '{0x%016xULL,0x%016xULL,0x%016xULL,%s},\n' %
                (*row[:3], 'true' if row[3] else 'false') for row in rows) + '};\n')
        flags = ['-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-fno-exceptions',
                 '-fno-rtti', '-fno-builtin', '-ffunction-sections', '-fdata-sections',
                 '-Wl,--gc-sections', '-I' + str(temp), '-I' + str(source / 'runtime')]
        inputs = [str(Path(__file__).with_name('ctr_pow_test.cc')),
                  str(source / 'runtime/vm/ctr_double_helpers.cc')]
        compiler = 'g++'
        if native:
            (temp / 'start.S').write_text(START.replace('cmp r1, #0x00080000', 'cmp r1, #0x20000000'))
            flags += [*profile['cflags'], '-D__3DS__', '-DCTR_POW_FREESTANDING',
                      '-nostdlib', '-static', '-Wl,-e,_start', '-Wl,--build-id=none']
            inputs += [str(temp / 'start.S'), '-lgcc']
            compiler = profile['compiler_prefix'] + 'g++'
        binary = temp / 'pow-test'
        subprocess.run([compiler, *flags, *inputs, '-o', str(binary)], check=True)
        if native:
            disassembly = subprocess.check_output([
                profile['compiler_prefix'] + 'objdump', '-d', str(binary)], text=True)
            assert '<CtrDoublePowSpecial>:' in disassembly
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
        print(f'PASS {len(rows)} dynamic power shortcuts: ' + ('ARM11 FZ/DN and ABI (not CTR)' if native else 'host'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args()
    run(args.source, args.native)
