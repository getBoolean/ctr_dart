"""Execute the actual CTR symbol backend; native checks are compile/link evidence."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def run_host(source):
    fixture = Path(__file__).parent / 'ctr_symbols_host'
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'symbols-test'
        subprocess.run([
            'g++', '-std=c++20', '-fsanitize=address,undefined',
            '-fno-omit-frame-pointer', '-no-pie',
            '-I' + str(fixture), '-I' + str(source / 'runtime'),
            str(source / 'runtime/vm/native_symbol_ctr.cc'),
            str(fixture / 'test.cc'), str(fixture / 'image.S'),
            '-D_start=ctr_test_image_start',
            '-D__bss_end__=ctr_test_image_end',
            '-o', str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)


def run_native(source):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    fixture = Path(__file__).parent / 'ctr_symbols_host'
    with tempfile.TemporaryDirectory() as directory:
        for mode in ('jit', 'aot'):
            obj = Path(directory) / (mode + '.o')
            compile_command = [
                profile['compiler_prefix'] + 'g++', '-std=c++20',
                '-D__3DS__', '-DNDEBUG', '-DTARGET_ARCH_ARM',
                '-DDART_TARGET_ARMV6K', '-DARM_FPU_vfp',
                *(['-DDART_PRECOMPILED_RUNTIME'] if mode == 'aot' else []),
                *profile['cflags'], '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-parameter', '-Wno-missing-field-initializers',
                '-Wno-comments', '-I' + profile['libctru'] + '/include',
                '-I' + str(source / 'runtime'), '-I' + str(source),
            ]
            subprocess.run(compile_command + [
                '-c', str(source / 'runtime/vm/native_symbol_ctr.cc'),
                '-o', str(obj)], check=True)
            symbols = subprocess.check_output([
                profile['compiler_prefix'] + 'nm', '-C', str(obj)], text=True)
            for method in ('Init', 'Cleanup', 'AddSymbols', 'LookupSymbolName',
                           'LookupSharedObject', 'FreeSymbolName'):
                assert 'T dart::NativeSymbolResolver::' + method + '(' in symbols
            assert ' U _start' in symbols and ' U __bss_end__' in symbols
            assert '__start__' not in symbols and 'dladdr' not in symbols
            print('PASS native ' + mode + ' resolver exports and relocated bounds')
            elf = Path(directory) / (mode + '.elf')
            subprocess.run(compile_command + [
                '-specs=3dsx.specs', str(obj), str(fixture / 'native_probe.cc'),
                '-L' + profile['libctru'] + '/lib', '-lctru', '-o', str(elf),
            ], check=True)
            table = subprocess.check_output([
                profile['compiler_prefix'] + 'readelf', '-sW', str(elf)], text=True)
            for name, section in (('__start__', 'ABS'), ('_start', '1')):
                row = next(line.split() for line in table.splitlines()
                           if line.split() and line.split()[-1] == name)
                assert row[-2] == section, row
            row = next(line.split() for line in table.splitlines()
                       if line.split() and line.split()[-1] == '__bss_end__')
            assert row[-2].isdigit(), row
            subprocess.run(['/opt/devkitpro/tools/bin/3dsxtool', str(elf),
                            str(elf.with_suffix('.3dsx'))], check=True)
            print('PASS native ' + mode + ' SDK/libctru link and 3DSX conversion')
        obj = Path(directory) / 'linux.o'
        subprocess.run([
            'g++', '-std=c++20', '-DNDEBUG',
            '-I' + str(source / 'runtime'), '-I' + str(source),
            '-c', str(source / 'runtime/vm/native_symbol_ctr.cc'), '-o', str(obj),
        ], check=True)
        assert 'NativeSymbolResolver' not in subprocess.check_output(
            ['nm', '-C', str(obj)], text=True)
        print('PASS Linux backend exclusion')
    assert (source / 'runtime/vm/vm_sources.gni').read_text().count(
        '"native_symbol_ctr.cc"') == 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args()
    (run_native if args.native else run_host)(args.source)
