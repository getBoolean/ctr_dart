"""Run real math adapters and SDK power routing on ARM11; never CTR proof."""
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DEFAULT_PROFILE, file_hash
import soft_math
from libm_reference import NAMES, agrees, cases
from test_ctr_double import START


def run(source, output, mutation=False):
    rows, version = cases()
    profile = json.loads(DEFAULT_PROFILE.read_text())
    output.mkdir(parents=True, exist_ok=False)
    original = soft_math.BRIDGE
    try:
        if mutation:
            changed = output / 'wrong-pcs.cc'
            text = original.read_text()
            assert text.count('__attribute__((pcs("aapcs")))') == 2
            changed.write_text(text.replace('__attribute__((pcs("aapcs")))', ''))
            soft_math.BRIDGE = changed
        component, component_record = soft_math.prepare(
            output / 'component', profile, soft_math.provider_path(profile))
    finally:
        soft_math.BRIDGE = original
    projected = rows[:4] + rows[4::31]
    observed = [tuple(int(v, 16) for v in row) for row in re.findall(
        r'\[(0x[0-9a-f]+),(0x[0-9a-f]+),(0x[0-9a-f]+),(0x[0-9a-f]+)\]',
        (source / 'runtime/ctr/test/numeric_libm_cases.dart').read_text())]
    if observed != projected:
        raise AssertionError('Dart libm goldens differ from stabilized MPFR reference')
    (output / 'cases.h').write_text('struct Case {unsigned op; uint64_t x,y;};\n'
        'static const Case cases[]={\n' + ''.join(
            '{%d,0x%016xULL,0x%016xULL},\n' % row[:3] for row in rows) + '};\n')
    assert START.count('cmp r1, #0x00080000') == 1
    (output / 'start.S').write_text(START.replace('cmp r1, #0x00080000', 'cmp r1, #0x00100000'))
    functions = ['CtrDoublePow'] + ['CtrLibm' + name for name in NAMES[1:]]
    lines = ['#include <stdint.h>', '#include "vm/ctr_double_helpers.h"', '#include "cases.h"',
             'extern "C" void test_write(const char*,unsigned);',
             'extern "C" int test_abi(double (*)(double));',
             'static double value(uint64_t v){double x;__builtin_memcpy(&x,&v,8);return x;}']
    for op, function in enumerate(functions):
        lines.append(f'extern "C" double abi_{op}(double x){{(void){function}(x' +
                     (',1.0' if op in (0, 3) else '') + ');return x;}')
    lines += ['static double (*callbacks[])(double)={' +
              ','.join(f'abi_{op}' for op in range(len(functions))) + '};',
              'int main(){uint32_t f;asm volatile("vmrs %0,fpscr":"=r"(f));',
              'if((f&0x03000000)!=0x03000000)return 2;',
              'for(auto fn:callbacks)if(test_abi(fn))return 3;',
              'for(auto row:cases){double x=value(row.x),y=value(row.y),r;switch(row.op){']
    for op, function in enumerate(functions):
        lines.append(f'case {op}:r={function}(x' + (',y' if op in (0, 3) else '') + ');break;')
    lines += ['default:return 5;}test_write(reinterpret_cast<const char*>(&r),8);}',
              'asm volatile("vmrs %0,fpscr":"=r"(f));return (f&0x03000000)==0x03000000?0:4;}']
    (output / 'test.cc').write_text('\n'.join(lines) + '\n')
    binary = output / 'test'
    command = [profile['compiler_prefix'] + 'g++', '-std=c++20', '-O2', '-fno-builtin',
               '-fno-exceptions', '-fno-rtti', '-ffunction-sections', '-fdata-sections',
               *profile['cflags'], '-D__3DS__', '-I' + str(source / 'runtime'),
               '-nostdlib', '-static', '-Wl,--gc-sections', '-Wl,-e,_start',
               output / 'start.S', output / 'test.cc', Path(__file__).with_name('ctr_math_environment.cc'), component,
               source / 'runtime/vm/ctr_double_helpers.cc', '-lgcc', '-o', binary]
    subprocess.run(list(map(str, command)), check=True)
    disassembly = subprocess.check_output([
        profile['compiler_prefix'] + 'objdump', '-d', str(binary)], text=True)
    for block in re.split(r'\n(?=[0-9a-f]+ <)', disassembly):
        title = block.splitlines()[0] if block else ''
        for op in re.findall(r'^\s*[0-9a-f]+:\s+[0-9a-f]+\s+(\S+)', block, re.M):
            transport = op.startswith(('vmov', 'vldr', 'vstr', 'vpush', 'vpop'))
            control = ('<main>' in title or '<_start>' in title) and op in ('vmrs', 'vmsr')
            if ((op.startswith('v') and not transport and not control) or
                    op.startswith(('sdiv', 'udiv', 'movw', 'movt', 'dmb', 'dsb', 'isb'))):
                raise AssertionError(f'unassisted/unsupported instruction: {title}: {op}')
    result = subprocess.run(['qemu-arm', '-cpu', 'arm11mpcore', str(binary)],
                            capture_output=True, check=True, timeout=60)
    if len(result.stdout) != 8 * len(rows):
        raise AssertionError('incomplete native math output')
    actual = struct.unpack('<' + 'Q' * len(rows), result.stdout)
    for index, (row, value) in enumerate(zip(rows, actual)):
        if not agrees(row[0], value, row[3]):
            raise AssertionError(f'libm mismatch case {index}: {NAMES[row[0]]} '
                                 f'actual={value:016x} expected={row[3]:016x}')
    record = {'scope': 'ARM11 QEMU only; not CTR execution', 'count': len(rows),
              'mpfr': version, 'reference_precisions': [256, 512],
              'fixture_sha256': file_hash(binary), 'component': component_record,
              'helper_sha256': file_hash(source / 'runtime/vm/ctr_double_helpers.cc'),
              'policy': 'special values and integral rounding exact; finite nonzero math <=2 ULP'}
    (output / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'PASS {len(rows)} MPFR math cases, 14 ABI adapters and FZ/DN (not CTR)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--mutation', action='store_true')
    args = parser.parse_args()
    if args.output:
        run(args.source, args.output, args.mutation)
    else:
        with tempfile.TemporaryDirectory() as directory:
            run(args.source, Path(directory) / 'run', args.mutation)
