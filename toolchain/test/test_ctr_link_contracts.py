"""Exercise actual CTR basename code and link it against the pinned native libc."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def run(source):
    toolchain = Path(__file__).parents[1]
    profile = json.loads((toolchain / 'target-ctr.json').read_text())
    fixture = Path(__file__).parent / 'ctr_link_host/basename_test.cc'
    sources = [fixture, source / 'runtime/platform/utils.cc',
               source / 'runtime/platform/utils_ctr.cc']
    flags = ['-std=c++20', '-O2', '-DNDEBUG', '-D__3DS__',
             '-ffunction-sections', '-fdata-sections',
             '-I' + str(source / 'runtime'), '-I' + str(source),
             '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter']
    with tempfile.TemporaryDirectory(prefix='ctr-link-contracts-') as directory:
        binary = Path(directory) / 'basename-host'
        subprocess.run([str(source / 'buildtools/linux-x64/clang/bin/clang++'),
                        '-I' + str(toolchain / 'test/ctr_sync_host'),
                        *flags, *map(str, sources), '-Wl,--gc-sections',
                        '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
        native = Path(directory) / 'basename.elf'
        subprocess.run([profile['compiler_prefix'] + 'g++', *flags,
                        '-DTARGET_ARCH_ARM', '-DARM_FPU_' + profile['arm_fpu'],
                        *profile['cflags'], '-I' + profile['libctru'] + '/include',
                        *map(str, sources), '-specs=' + str(toolchain / 'ctr.specs'),
                        '-Wl,--gc-sections', '-L' + profile['libctru'] + '/lib',
                        '-lctru', '-lm', '-o', str(native)], check=True)
        print('PASS pinned native basename ELF link (not executed on CTR)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    run(parser.parse_args().source.resolve())
