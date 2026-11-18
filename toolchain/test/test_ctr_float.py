"""Check real scalar float bridges against IEEE host oracles; QEMU is not CTR."""
import argparse
import json
from pathlib import Path
import random
import re
import struct
import subprocess
import tempfile

from test_ctr_double import START, bits, number


def float_bits(value):
    try:
        return struct.unpack('<I', struct.pack('<f', value))[0]
    except OverflowError:
        return 0xff800000 if value < 0 else 0x7f800000


def cases():
    doubles = [0, 1, 0x000fffffffffffff, 0x0010000000000000,
               0x3690000000000000, 0x36a0000000000000, 0x36b0000000000000,
               0x380fffffc0000000, 0x3810000000000000, 0x3ff0000010000000,
               0x3ff0000030000000, bits(1), bits(1.5), bits(2),
               0x47efffffe0000000, 0x7fefffffffffffff,
               0x7ff0000000000000, 0x7ff0000000000001, 0x7ff8000000000000]
    singles = [0, 1, 2, 0x007fffff, 0x00800000, 0x3f800000,
               0x7f7fffff, 0x7f800000, 0x7f800001, 0x7fc00000]
    doubles += [v | (1 << 63) for v in doubles]
    singles += [v | (1 << 31) for v in singles]
    rng = random.Random(0x435452463332)
    doubles += [rng.getrandbits(64) for _ in range(8192)]
    singles += [rng.getrandbits(32) for _ in range(8192)]
    result = [(1, v, float_bits(number(v))) for v in doubles]
    result += [(0, v, bits(struct.unpack('<f', struct.pack('<I', v))[0])) for v in singles]
    return result


def run(source, native=False, baseline=False):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    rows = cases()
    golden = source / 'runtime/ctr/test/numeric_float_cases.dart'
    selected = ([row for row in rows if row[0]][:166] +
                [row for row in rows if not row[0]][:148])
    observed = [tuple(int(value, 0) for value in row) for row in re.findall(
        r'\[([01]),(0x[0-9a-f]+),(0x[0-9a-f]+)\]', golden.read_text())]
    if observed != selected:
        raise AssertionError('Dart float goldens differ from the independent host oracle')
    with tempfile.TemporaryDirectory(prefix='ctr-float-') as directory:
        temp = Path(directory)
        (temp / 'float_cases.h').write_text(
            'struct Case { intptr_t narrow; uint64_t input, expected; };\n'
            'static const Case cases[] = {\n' + ''.join(
                '{%d,0x%016xULL,0x%016xULL},\n' % row for row in rows) + '};\n')
        flags = ['-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-fno-exceptions', '-fno-rtti', '-fno-builtin',
                 '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                 '-I' + str(temp), '-I' + str(source / 'runtime')]
        inputs = [str(Path(__file__).with_name('ctr_float_test.cc'))]
        if baseline:
            flags.append('-DCTR_FLOAT_BASELINE')
        else:
            inputs.append(str(source / 'runtime/vm/ctr_double_helpers.cc'))
        if native:
            # The existing ABI probe supplies smallest-normal and two. This
            # roundtrip correctly underflows to zero instead of normal / two.
            assert START.count('cmp r1, #0x00080000') == 1
            (temp / 'start.S').write_text(START.replace('cmp r1, #0x00080000', 'cmp r1, #0'))
            flags += [*profile['cflags'], '-D__3DS__', '-DCTR_FLOAT_FREESTANDING',
                      '-nostdlib', '-static', '-Wl,-e,_start', '-Wl,--build-id=none']
            inputs += [str(temp / 'start.S'), '-lgcc']
            compiler = profile['compiler_prefix'] + 'g++'
        else:
            compiler = 'g++'
        binary = temp / 'float-test'
        subprocess.run([compiler, *flags, *inputs, '-o', str(binary)], check=True)
        if native and not baseline:
            disassembly = subprocess.check_output([
                profile['compiler_prefix'] + 'objdump', '-d', str(binary)], text=True)
            assert '<CtrFloatConvert>:' in disassembly
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
        print(f'PASS {len(rows)} float conversions: ' + ('ARM11 FZ/DN and ABI (not CTR)' if native else 'host'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    run(args.source, args.native, args.baseline)
