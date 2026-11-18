"""Compile actual CTR ABI/fence boundaries; host execution is not CTR execution."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile


def check_fence(disassembly):
    # ARM11 data memory barrier, not merely a compiler-only fence.
    if not re.search(r'mcr\s+15,\s*0,\s*r\d+,\s*cr7,\s*cr10,\s*\{5\}', disassembly):
        raise RuntimeError('ARM11 data memory barrier absent:\n' + disassembly)
    before, after = disassembly.split('mcr', 1)
    if '#42' not in before or not re.search(r'\bstr\b', before):
        raise RuntimeError('pre-fence store was eliminated or moved:\n' + disassembly)
    if '#43' not in after or not re.search(r'\bstr\b', after):
        raise RuntimeError('post-fence store absent:\n' + disassembly)


def run(source, native):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    fixture = Path(__file__).parent / 'ctr_runtime_integration'
    flags = ['-std=c++20', '-DNDEBUG', '-DTARGET_ARCH_ARM',
             '-DDART_TARGET_OS_CTR', '-Wall', '-Wextra', '-Werror',
             '-Wno-unused-parameter', '-I' + str(source / 'runtime'),
             '-I' + str(source)]
    compiler = 'g++'
    if native:
        compiler = profile['compiler_prefix'] + 'g++'
        flags += ['-D__3DS__', *profile['cflags'],
                  '-I' + profile['libctru'] + '/include']
    else:
        flags += ['-include', 'cstddef']
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'abi'
        command = [compiler, *flags, str(fixture / 'abi.cc'),
                   str(source / 'runtime/vm/compiler/ffi/abi.cc'), '-o', str(binary)]
        if native:
            # Each translation unit has its own output under cross compilation.
            command = [compiler, *flags, '-c', str(fixture / 'abi.cc'), '-o', str(binary)]
        subprocess.run(command, check=True)
        if not native:
            subprocess.run([str(binary)], check=True)
        else:
            # Keep fixture assertions active: native compilation checks ICU's
            # real newlib typedef boundaries, without claiming execution.
            subprocess.run([compiler, *flags, '-UNDEBUG', '-DU_HAVE_MMAP=0',
                            '-I' + str(source / 'third_party/icu/source/common'),
                            '-c', str(fixture / 'icu.cc'), '-o', str(binary)], check=True)
            subprocess.run([compiler, *flags, '-O2', '-c', str(fixture / 'fence.cc'),
                            '-o', str(binary)], check=True)
            disassembly = subprocess.check_output(
                [profile['compiler_prefix'] + 'objdump', '-d', str(binary)], text=True)
            check_fence(disassembly)
            print(disassembly)
    print('PASS native ABI layout and fence' if native else 'PASS host CTR ABI selection')


def run_dart(source):
    fixture = Path(__file__).parent / 'ctr_runtime_integration' / 'abi.dart'
    with tempfile.TemporaryDirectory() as directory:
        test = Path(directory) / 'abi.dart'
        uri = (source / 'pkg/vm/lib/modular/transformations/ffi/abi.dart').as_uri()
        test.write_text(fixture.read_text().replace('SDK_ABI_URI', uri))
        subprocess.run([source / 'tools/sdks/dart-sdk/bin/dart',
                        '--packages=' + str(source / '.dart_tool/package_config.json'),
                        test], check=True)


def run_icu(source, output):
    icu = source / 'third_party/icu/source/common'
    objects = [str(path) for path in output.rglob('icuuc.*.o')
               if path.name != 'icuuc.umapfile.o']
    if not objects:
        raise RuntimeError('build the pinned host ICU common graph first')
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'icu'
        subprocess.run(['g++', '-std=c++20', '-DU_HAVE_MMAP=0',
                        '-DU_STATIC_IMPLEMENTATION', '-DU_COMMON_IMPLEMENTATION',
                        '-I' + str(icu), str(Path(__file__).parent /
                        'ctr_runtime_integration/icu.cc'), str(icu / 'umapfile.cpp'),
                        *objects, '-pthread', '-ldl', '-o', str(binary)], check=True)
        subprocess.run([str(binary), str(Path(directory) / 'data.bin')], check=True)


def check_archive(symbols):
    # These real runtime interfaces must travel with a complete native archive.
    for symbol in ['dart::OS::GetCurrentTimeMicros()',
                   'dart::OSThread::Start(',
                   'dart::VirtualMemory::AllocateAligned(',
                   'dart::CPU::FlushICache(']:
        if symbol not in symbols:
            raise RuntimeError('native archive lacks ' + symbol)


def run_archive(archive):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    symbols = subprocess.check_output([profile['compiler_prefix'] + 'nm',
                                      '-g', '-C', '--defined-only', archive], text=True)
    check_archive(symbols)
    print('PASS complete native runtime archive interfaces (not an executable link)')


def run_host_shared(source, output):
    commands = subprocess.check_output([
        str(source / 'buildtools/ninja/ninja'), '-C', str(output),
        '-t', 'commands', 'dart_jit_library'], text=True)
    links = [line for line in commands.splitlines()
             if '-Wl,-soname=libdart_jit.so' in line and ' -shared ' in line]
    if len(links) != 1 or '--target=x86_64-linux-gnu' not in links[0]:
        raise RuntimeError('expected one actual Linux host shared-VM link command')
    if '-install_name' in links[0]:
        raise RuntimeError('Linux host VM link includes a macOS install_name flag:\n' + links[0])
    print('PASS Linux host shared-VM link flags (not an executable link)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true')
    parser.add_argument('--dart', action='store_true', help='execute actual transformer ABI tables on host')
    parser.add_argument('--icu-host-output', type=Path, help='pinned host ICU build output')
    parser.add_argument('--archive', type=Path, help='check the actual native static archive boundary')
    parser.add_argument('--host-shared-output', type=Path,
                        help='check a Linux GN graph rooted at //runtime:dart_jit_library')
    args = parser.parse_args()
    if args.host_shared_output:
        run_host_shared(args.source.resolve(), args.host_shared_output.resolve())
    elif args.archive:
        run_archive(args.archive.resolve())
    elif args.icu_host_output:
        run_icu(args.source.resolve(), args.icu_host_output.resolve())
    elif args.dart:
        run_dart(args.source.resolve())
    else:
        run(args.source.resolve(), args.native)
