"""Compile actual CTR memory adapters; host service injection is not target proof."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def run_host(source):
    fixture = Path(__file__).parent / 'ctr_memory_host'
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'memory-test'
        subprocess.run([
            'g++', '-std=c++20', '-D__3DS__', '-DDEBUG',
            '-I' + str(fixture), '-I' + str(fixture.parent / 'ctr_sync_host'),
            '-I' + str(source / 'runtime'),
            str(source / 'runtime/vm/virtual_memory.cc'),
            str(source / 'runtime/vm/virtual_memory_ctr.cc'),
            str(source / 'runtime/vm/cpu_cache_ctr.cc'),
            str(fixture / 'test.cc'), '-Wl,--wrap=memalign', '-Wl,--wrap=free',
            '-o', str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)


def run_native(source):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    selections = (source / 'runtime/vm/vm_sources.gni').read_text()
    for name in ('virtual_memory_ctr.cc', 'cpu_cache_ctr.cc', 'cpu_arm.cc'):
        assert selections.count('"' + name + '"') == 1, name
    with tempfile.TemporaryDirectory() as directory:
        for mode in ('jit', 'aot'):
            for path in ('vm/virtual_memory_ctr.cc', 'vm/virtual_memory.cc',
                         'vm/cpu_cache_ctr.cc', 'vm/cpu_arm.cc',
                         'vm/virtual_memory_posix.cc', 'vm/virtual_memory_fuchsia.cc'):
                obj = Path(directory) / (Path(path).name + '.o')
                subprocess.run([
                    profile['compiler_prefix'] + 'g++', '-std=c++20',
                    '-D__3DS__', '-DNDEBUG', '-DTARGET_ARCH_ARM',
                    '-DDART_TARGET_ARMV6K', '-DARM_FPU_' + profile['arm_fpu'],
                    *(['-DDART_PRECOMPILED_RUNTIME'] if mode == 'aot' else []),
                    *profile['cflags'], '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-parameter', '-Wno-missing-field-initializers',
                    '-Wno-comments', '-I' + profile['libctru'] + '/include',
                    '-I' + str(source / 'runtime'), '-I' + str(source),
                    '-c', str(source / 'runtime' / path),
                    '-o', str(obj),
                ], check=True)
                symbols = subprocess.check_output([
                    profile['compiler_prefix'] + 'nm', '-C', str(obj)], text=True)
                if path.endswith('cpu_arm.cc'):
                    assert ('U dart::CtrFlushICache(' in symbols) == (mode == 'jit')
                elif path.endswith('cpu_cache_ctr.cc'):
                    assert 'T DartCtrFlushEntireCache' in symbols
                    assembly = subprocess.check_output([
                        profile['compiler_prefix'] + 'objdump', '-d', str(obj)], text=True)
                    for instruction in ('ef000080', 'ee070f1a', 'ee070f9a',
                                        'ee070f15', 'ee070f95'):
                        assert instruction in assembly, instruction
                elif path.endswith('virtual_memory_ctr.cc'):
                    assert 'T dart::VirtualMemory::Protect(' in symbols
                elif path.endswith(('virtual_memory_posix.cc', 'virtual_memory_fuchsia.cc')):
                    assert 'dart::VirtualMemory::' not in symbols
                print('PASS ' + mode + ' ' + path, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args()
    (run_native if args.native else run_host)(args.source)
