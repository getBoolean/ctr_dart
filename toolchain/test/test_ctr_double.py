"""Check actual helper bits/ABI under QEMU; this is never CTR execution."""
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
import math
from pathlib import Path
import random
import re
import struct
import subprocess
import tempfile


def bits(value):
    return struct.unpack('<Q', struct.pack('<d', value))[0]


def number(value):
    return struct.unpack('<d', struct.pack('<Q', value))[0]


def cases():
    # Independent bit-exact anchors include halfway rounding and signed zero.
    result = [(3, 0x0010000000000000, bits(2.0), 0x0008000000000000),
              (3, 0x8010000000000000, bits(2.0), 0x8008000000000000),
              (0, 1, 1, 2), (1, 0x0010000000000000, 1, 0x000fffffffffffff),
              (2, 1, bits(0.5), 0), (2, 3, bits(0.5), 2),
              (2, 0x1ff0000000000000, 0x1ff0000000000000, 0x0004000000000000),
              (0, 0x8000000000000000, 0x8000000000000000, 0x8000000000000000)]
    edges = [0, 1, 2, 3, 0x000fffffffffffff, 0x0010000000000000,
             bits(0.5), bits(1.0), bits(2.0), 0x7fefffffffffffff,
             0x7ff0000000000000, 0x7ff8000000000001, 0x7ff0000000000001]
    edges += [x | (1 << 63) for x in edges]
    rng = random.Random(0x435452)
    pairs = [(a, b) for a in edges for b in edges]
    pairs += [(rng.getrandbits(64), rng.getrandbits(64)) for _ in range(2048)]
    for a, b in pairs:
        x, y = number(a), number(b)
        for op in range(4):
            if op == 3 and y == 0:
                expected = (math.nan if x == 0 or math.isnan(x) else
                            math.copysign(math.inf, math.copysign(1, x) * math.copysign(1, y)))
            else:
                expected = [lambda: x + y, lambda: x - y,
                            lambda: x * y, lambda: x / y][op]()
            result.append((op, a, b, bits(expected)))
    return result


START = '''.syntax unified
.arm
.fpu vfp
.global _start
_start:
  mov r0, #0x03000000
  vmsr fpscr, r0
  bl main
  mov r7, #1
  svc #0
.global test_write
test_write:
  mov r2, r1
  mov r1, r0
  mov r0, #1
  push {r7, lr}
  mov r7, #4
  svc #0
  pop {r7, pc}
.global test_abort
test_abort:
  mov r0, #125
  mov r7, #1
  svc #0
  b .
.global memcpy
memcpy:
  mov r3, r0
1:
  cmp r2, #0
  bxeq lr
  ldrb ip, [r1], #1
  strb ip, [r3], #1
  subs r2, r2, #1
  b 1b
.global test_abi
test_abi:
  push {r4-r11, lr}
  sub sp, sp, #4
  vpush {d8-d15}
  mov r2, #0x35
  mov r3, #0x36
  vmov d8, r2, r3
  vmov d9, r2, r3
  vmov d10, r2, r3
  vmov d11, r2, r3
  vmov d12, r2, r3
  vmov d13, r2, r3
  vmov d14, r2, r3
  vmov d15, r2, r3
  mov r4, #0x37
  mov r5, #0x37
  mov r6, #0x37
  mov r7, #0x37
  mov r8, #0x37
  mov r9, #0x37
  mov r10, #0x37
  mov r11, #0x37
  mov r1, #0
  mov r2, #0x00100000
  vmov d0, r1, r2
  mov r2, #0x40000000
  vmov d1, r1, r2
  blx r0
  vmov r0, r1, d0
  cmp r0, #0
  bne 2f
  cmp r1, #0x00080000
  bne 2f
  cmp r4, #0x37
  bne 2f
  cmp r5, #0x37
  bne 2f
  cmp r6, #0x37
  bne 2f
  cmp r7, #0x37
  bne 2f
  cmp r8, #0x37
  bne 2f
  cmp r9, #0x37
  bne 2f
  cmp r10, #0x37
  bne 2f
  cmp r11, #0x37
  bne 2f
''' + ''.join(f'''  vmov r0, r1, d{register}
  cmp r0, #0x35
  bne 2f
  cmp r1, #0x36
  bne 2f
''' for register in range(8, 16)) + '''  mov r0, #0
  b 3f
2:
  mov r0, #3
3:
  vpop {d8-d15}
  add sp, sp, #4
  pop {r4-r11, pc}
.section .note.GNU-stack,"",%progbits
'''


def run(source, baseline=False, native=False):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    data = cases()
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        (temp / 'numeric_cases.h').write_text(
            'struct NumericCase { unsigned op; uint64_t a, b, expected; };\n'
            'static const NumericCase cases[] = {\n' + ''.join(
                '{%d,0x%016xULL,0x%016xULL,0x%016xULL},\n' % row for row in data) + '};\n')
        binary = temp / 'numeric-test'
        flags = ['-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                 '-fno-exceptions', '-fno-rtti', '-fno-builtin',
                 '-I' + str(temp), '-I' + str(source / 'runtime')]
        inputs = [str(source / 'runtime/vm/ctr_double_helpers_test.cc')]
        if baseline:
            flags += ['-DCTR_DOUBLE_BASELINE']
        else:
            inputs += [str(source / 'runtime/vm/ctr_double_helpers.cc')]
        if native:
            if not baseline:
                import sys
                sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
                from soft_math import prepare, provider_path
                component, _ = prepare(temp / 'math-component', profile, provider_path(profile))
                inputs += [str(component), str(Path(__file__).with_name('ctr_math_environment.cc'))]
                # Keep all SDK helpers in their original text section for the
                # audit; discard only unused private provider sections.
                flags += ['-Wl,--gc-sections']
            provider = Path(subprocess.check_output([
                profile['compiler_prefix'] + 'gcc', *profile['cflags'],
                '-print-libgcc-file-name'], text=True).strip())
            print('libgcc sha256=' + hashlib.sha256(provider.read_bytes()).hexdigest(), flush=True)
            (temp / 'start.S').write_text(START)
            flags += [*profile['cflags'], '-D__3DS__', '-DCTR_DOUBLE_FREESTANDING',
                      '-nostdlib', '-static', '-Wl,-e,_start', '-Wl,--build-id=none']
            inputs += [str(temp / 'start.S'), '-lgcc']
            compiler = profile['compiler_prefix'] + 'g++'
        else:
            compiler = 'g++'
        subprocess.run([compiler, *flags, *inputs, '-o', str(binary)], check=True)
        if native and not baseline:
            # Audit only linked production helper/provider functions, not test code.
            disassembly = subprocess.check_output([
                profile['compiler_prefix'] + 'objdump', '-d', str(binary)], text=True)
            seen = []
            for block in re.split(r'\n(?=[0-9a-f]+ <)', disassembly):
                title = block.splitlines()[0] if block else ''
                if re.search(r'<(?:CtrDouble|__aeabi_d|__adddf|__subdf|__muldf|__divdf)', title):
                    seen.append(title)
                    # VFP is transport only. Also reject ARMv7/idiv/NEON instructions.
                    mnemonics = re.findall(r'^\s*[0-9a-f]+:\s+[0-9a-f]+\s+(\S+)', block, re.M)
                    for mnemonic in mnemonics:
                        if (mnemonic.startswith('v') and not mnemonic.startswith(
                                ('vmov', 'vldr', 'vstr', 'vpush', 'vpop')) or
                                mnemonic.startswith(('sdiv', 'udiv', 'movw', 'movt', 'dmb', 'dsb', 'isb'))):
                            raise AssertionError(f'unsupported/flushing instruction: {title}: {mnemonic}')
            if len(seen) < 8:
                raise AssertionError(f'provider/bridge audit incomplete: {seen}')
            print(f'PASS disassembly: {len(seen)} linked bridge/provider functions; transport-only VFP')
        command = ['qemu-arm', '-cpu', 'arm11mpcore', str(binary)] if native else [str(binary)]
        subprocess.run(command, check=True, timeout=30)
        print(f'PASS {len(data)} dynamic arithmetic cases: ' +
              ('ARM11 QEMU, hard-float ABI, FPSCR FZ/DN set (not CTR)' if native else 'host'))


def format_audit(source, native):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    edges = [1, 2, 3, 0x000ffffffffffffe, 0x000fffffffffffff,
             0x0010000000000000, 0x0010000000000001, 0, bits(0.1),
             bits(0.5), bits(1.0), bits(1e-6), bits(1e21), bits(1e60),
             0x7fefffffffffffff, 0x7ff0000000000000, 0x7ff8000000000001,
             0x7ff0000000000001]
    rng = random.Random(0xdec1a1)
    values = edges + [x | (1 << 63) for x in edges]
    values += [rng.getrandbits(64) for _ in range(512)]
    values += [rng.getrandbits(52) | sign for sign in (0, 1 << 63) for _ in range(128)]
    texts = ['5e-324', '-5e-324', '2.4703282292062327e-324',
             '2.4703282292062328e-324', '2.2250738585072011e-308',
             '2.2250738585072012e-308', '2.2250738585072014e-308',
             '1.7976931348623157e308', '1.7976931348623159e308',
             '-1e-999', '1e999', '-0', '0', '9007199254740993',
             '1.00000000000000011102230246251565404236316680908203125',
             '1.00000000000000011102230246251565404236316680908203126']
    texts += [repr(number(x)) for x in values if math.isfinite(number(x))]
    with localcontext() as context:
        context.prec = 1200
        texts += [format(Decimal(2) ** -1075, 'f'),
                  format(Decimal(2) ** -1075 + Decimal(10) ** -1100, 'f')]
        texts += [format(Decimal.from_float(number(x)), 'f') for x in edges[:7]]
    singles = [0, 1, 2, 3, 0x007fffff, 0x00800000, 0x00800001,
               0x3f000000, 0x3f800000, 0x7f7fffff, 0x7f800000]
    singles += [x | 0x80000000 for x in singles]
    single_texts = [repr(struct.unpack('<f', struct.pack('<I', x))[0])
                    .replace('inf', 'Infinity') for x in singles]
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        (temp / 'decimal_cases.h').write_text(
            'static const uint64_t format_cases[] = {\n' +
            ''.join('0x%016xULL,\n' % x for x in values) + '};\n' +
            'struct ParseCase { const char* text; uint64_t expected; };\n'
            'static const ParseCase parse_cases[] = {\n' +
            ''.join('{%s,0x%016xULL},\n' % (json.dumps(t), bits(float(t))) for t in texts) + '};\n' +
            'static const ParseCase single_cases[] = {\n' +
            ''.join('{%s,0x%08xULL},\n' % (json.dumps(t), x) for t, x in zip(single_texts, singles)) + '};\n')
        binary = temp / 'format-test'
        flags = ['-std=c++20', '-O2', '-ffunction-sections',
                 '-DDOUBLE_CONVERSION_ASSERT(condition)=((condition)?(void)0:abort())',
                 '-fdata-sections', '-Wl,--gc-sections', '-I' + str(source), '-I' + str(temp)]
        inputs = [str(Path(__file__).with_name('ctr_double_format_test.cc'))]
        inputs += [str(path) for path in sorted((source / 'third_party/double-conversion/src').glob('*.cc'))]
        # Host IEEE arithmetic is the independent oracle for exact formatting.
        host = temp / 'format-host'
        subprocess.run(['g++', *flags, *inputs, '-o', str(host)], check=True)
        expected = subprocess.check_output([str(host)], timeout=30)
        if not expected.startswith(b'5e-324\n'):
            raise AssertionError('smallest-subnormal golden failed on host')
        compiler = 'g++'
        if native:
            compiler = profile['compiler_prefix'] + 'g++'
            (temp / 'start.S').write_text(START)
            flags += [*profile['cflags'], '-D__3DS__', '-DCTR_DOUBLE_FREESTANDING', '-fno-exceptions',
                      '-fno-rtti', '-nostdlib', '-static', '-Wl,-e,_start']
            inputs += [str(source / 'runtime/vm/ctr_double_helpers.cc'),
                       '-I' + str(source / 'runtime'), str(temp / 'start.S'), '-Wl,--start-group', '-lc',
                       '-lgcc', '-Wl,--end-group']
        subprocess.run([compiler, *flags, *inputs, '-o', str(binary)], check=True)
        if native:
            disassembly = subprocess.check_output([
                profile['compiler_prefix'] + 'objdump', '-d', str(binary)], text=True)
            audited = 0
            for block in re.split(r'\n(?=[0-9a-f]+ <)', disassembly):
                title = block.splitlines()[0] if block else ''
                mnemonics = re.findall(
                    r'^\s*[0-9a-f]+:\s+(?:[0-9a-f]{4}(?:[0-9a-f]{4})?\s+)+(\S+)',
                    block, re.M)
                for mnemonic in mnemonics:
                    # Audit the entire linked executable, including providers and
                    # libc. Only register/memory transport and test FPSCR access
                    # may use VFP. There is no libm or syscall-stub exemption.
                    transport = ('vmov', 'vldr', 'vstr', 'vpush', 'vpop')
                    fpscr_test = ('<main>' in title or '<_start>' in title) and mnemonic in ('vmrs', 'vmsr')
                    if ((mnemonic.startswith('v') and not mnemonic.startswith(transport) and not fpscr_test) or
                            mnemonic.startswith(('sdiv', 'udiv', 'movw', 'movt', 'dmb', 'dsb', 'isb'))):
                        raise AssertionError(f'unassisted/unsupported instruction: {title}: {mnemonic}')
                audited += bool(mnemonics)
            for required in ('DoubleToAscii', 'BignumDtoa', 'FastDtoa', 'FastFixedDtoa',
                             'StringToIeee', 'StrtodTrimmed', '__aeabi_dmul', '__aeabi_ddiv',
                             '__aeabi_d2f', '__aeabi_f2d'):
                if required not in disassembly:
                    raise AssertionError(f'decimal audit missing linked production path: {required}')
            print(f'PASS linked decimal audit: {audited} functions; transport-only VFP, no libm/syscall stubs')
        command = ['qemu-arm', '-cpu', 'arm11mpcore', str(binary)] if native else [str(binary)]
        result = subprocess.run(command, capture_output=True, timeout=60)
        if result.returncode or result.stdout != expected:
            got, want = result.stdout.splitlines(), expected.splitlines()
            mismatch = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
            raise AssertionError(f'decimal mismatch at output {mismatch}: '
                                 f'actual={got[mismatch:mismatch+1]} expected={want[mismatch:mismatch+1]}; '
                                 f'exit={result.returncode}; stderr={result.stderr.decode()}')
        print(f'PASS {len(values)} dynamic values, 16 format/fallback modes, '
              f'{len(texts)} independent parse goldens, {len(singles)} float roundtrips; ' +
              ('ARM11 QEMU FZ/DN (not CTR)' if native else 'host'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--baseline', action='store_true', help='characterize unassisted native arithmetic')
    parser.add_argument('--format-audit', action='store_true', help='check the actual SDK decimal library against host/golden results')
    args = parser.parse_args()
    if args.format_audit:
        format_audit(args.source, args.native)
    else:
        run(args.source, args.baseline, args.native)
