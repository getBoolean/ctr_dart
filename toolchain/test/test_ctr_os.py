"""Execute host adapter tests and cross-compile CTR sources (no device claim)."""
import argparse
import json
import signal
from pathlib import Path
import subprocess
import tempfile


def run_host(source):
    fixture = Path(__file__).parent / 'ctr_sync_host'
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'sync-test'
        subprocess.run([
            'g++', '-std=c++20', '-pthread', '-D__3DS__', '-DDEBUG',
            '-I' + str(fixture), '-I' + str(source / 'runtime'),
            str(source / 'runtime/platform/synchronization_ctr.cc'),
            str(fixture / 'test.cc'), '-o', str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
        subprocess.run([
            'g++', '-std=c++20', '-pthread', '-D__3DS__', '-DDEBUG',
            '-DDART_DISABLE_TIMELINE', '-ffunction-sections', '-fdata-sections',
            '-I' + str(fixture), '-I' + str(source / 'runtime'), '-I' + str(source),
            str(source / 'runtime/vm/os_ctr.cc'),
            str(source / 'runtime/platform/synchronization_ctr.cc'),
            str(fixture / 'os_test.cc'), '-Wl,--gc-sections',
            '-Wl,--wrap=clock_gettime', '-o', str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)


def run_lifecycle(source):
    fixture = Path(__file__).parent / 'ctr_thread_host'
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'thread-test'
        command = [
            'g++', '-std=c++20', '-pthread', '-D__3DS__', '-DDEBUG',
            '-DDART_DISABLE_TIMELINE', '-no-pie',
            '-I' + str(fixture), '-I' + str(fixture.parent / 'ctr_sync_host'),
            '-I' + str(source / 'runtime'),
            str(source / 'runtime/vm/os_thread_ctr.cc'),
            str(source / 'runtime/platform/synchronization_ctr.cc'),
            str(fixture / 'test.cc'),
        ]
        subprocess.run([*command, '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
        subprocess.run([str(binary), 'creation-failure'], check=True, timeout=10)
        unsupported = Path(directory) / 'unsupported-tls'
        subprocess.run([*command, '-DCTR_TEST_TLS_ALIGNMENT=16',
                        '-o', str(unsupported)], check=True)
        rejected = subprocess.run([str(unsupported)], text=True,
                                  capture_output=True, timeout=10)
        if rejected.returncode != -signal.SIGABRT or '__tdata_align' not in rejected.stderr:
            raise RuntimeError('unsupported TLS alignment was not rejected at the TLS boundary')


def run_native(source):
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    sources = [
        'platform/synchronization_ctr.cc', 'platform/utils_ctr.cc',
        'platform/utils.cc', 'platform/syslog_ctr.cc', 'vm/os_thread_ctr.cc',
        'vm/cpuinfo_ctr.cc', 'vm/thread_interrupter_ctr.cc', 'vm/os_ctr.cc',
        'vm/os_thread.cc', 'vm/random.cc', 'vm/os_thread_ctr_test.cc',
        'lib/ffi_dynamic_library.cc',
    ]
    failed = []
    with tempfile.TemporaryDirectory() as directory:
        for path in sources:
            result = subprocess.run([
                profile['compiler_prefix'] + 'g++', '-std=c++20',
                '-D__3DS__', '-DNDEBUG', '-DTESTING', '-DTARGET_ARCH_ARM',
                '-DARM_FPU_' + profile['arm_fpu'], *profile['cflags'],
                '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                '-Wno-missing-field-initializers', '-Wno-comments',
                '-I' + profile['libctru'] + '/include',
                '-I' + str(source / 'runtime'), '-I' + str(source),
                '-ffunction-sections', '-fdata-sections', '-c',
                str(source / 'runtime' / path), '-o',
                str(Path(directory) / (Path(path).name + '.o')),
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(('FAIL ' if result.returncode else 'PASS ') + path, flush=True)
            if result.returncode:
                print(result.stdout, flush=True)
                failed.append(path)
        if failed:
            raise RuntimeError('Native compilation failed: ' + ', '.join(failed))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--native', action='store_true', help='cross-compile; never execute target code')
    parser.add_argument('--lifecycle', action='store_true', help='execute native ownership adapter with host scheduling')
    args = parser.parse_args()
    if args.native:
        run_native(args.source)
    elif args.lifecycle:
        run_lifecycle(args.source)
    else:
        run_host(args.source)
        run_lifecycle(args.source)
