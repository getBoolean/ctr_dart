"""Compile real profiler callers and inspect their ELF symbols (no CTR execution)."""
import argparse
import json
import re
from pathlib import Path
import shlex
import subprocess


def check_archives(archives, output):
    """Resolve archive-internal definitions before checking external imports."""
    output.mkdir(parents=True, exist_ok=True)
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    prefix = profile['compiler_prefix']
    for index, archive in enumerate(archives):
        obj = output / f'archive-{index}.o'
        subprocess.run([prefix + 'ld', '-r', '--whole-archive', str(archive),
                        '--no-whole-archive', '-o', str(obj)], check=True)
        symbols = subprocess.check_output([prefix + 'nm', '-u', '-C', str(obj)], text=True)
        (output / f'archive-{index}-imports.txt').write_text(symbols)
        unwanted = [line for line in symbols.splitlines()
                    if re.search(r'dart::(?:Profiler|ProfilerService|Profile|ProfileFunction|SampleBlock|SampleBlockBuffer)::', line)]
        if unwanted:
            raise AssertionError(str(archive) + ':\n' + '\n'.join(unwanted))
        print(f'PASS whole archive has no profiler imports: {archive}', flush=True)


def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def execute_bodies(source, output):
    profiler = (source / 'runtime/vm/profiler.cc').read_text()
    service = (source / 'runtime/vm/service.cc').read_text()
    bodies = [function(profiler, signature) for signature in (
        'static void FlushSampleBlocks(', 'void Profiler::IsolateShutdown(',
        'void Profiler::IsolateGroupShutdown(')]
    bodies += [function(service, 'static void ' + name + '(') for name in (
        'EnableProfiler', 'ClearCpuSamples', 'GetCpuSamplesCommon',
        'GetAllocationTraces', 'SetTraceClassAllocation')]
    fixture = Path(__file__).with_name('ctr_profiler_host.cc').read_text()
    test = output / 'function-bodies.cc'
    test.write_text(fixture.replace('// SDK_FUNCTIONS', '\n\n'.join(bodies)))
    compiler = source / 'buildtools/linux-x64/clang/bin/clang++'
    for name, flags in (('no-timeline', []), ('timeline', ['-DSUPPORT_TIMELINE']),
                        ('perfetto', ['-DSUPPORT_TIMELINE', '-DSUPPORT_PERFETTO']),
                        ('perfetto-aot', ['-DSUPPORT_TIMELINE', '-DSUPPORT_PERFETTO',
                                          '-DDART_PRECOMPILED_RUNTIME'])):
        binary = output / name
        subprocess.run([str(compiler), '-std=c++20', '-Wall', '-Werror', *flags,
                        str(test), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        print(f'PASS lifecycle flush and disabled service bodies: {name}', flush=True)


def run(source, native_aot, native_jit, host, output):
    output.mkdir(parents=True, exist_ok=True)
    ninja = source / 'buildtools/ninja/ninja'
    nm = source / 'buildtools/linux-x64/clang/bin/llvm-nm'
    failures = []
    cases = [(native_aot, 'obj/runtime/vm/libdart_vm_aotruntime', 'aot'),
             (native_jit, 'obj/runtime/vm/libdart_vm_jit', 'jit')]
    for build, prefix, mode in cases:
        for unit in (('object', 'service', 'source_report') if mode == 'jit'
                     else ('object', 'service')):
            obj = compile_unit(source, ninja, build, prefix, unit,
                               output / f'{mode}-{unit}.o')
            symbols = subprocess.check_output([str(nm), '-u', '-C', str(obj)], text=True)
            unwanted = [line for line in symbols.splitlines()
                        if 'dart::Profiler::' in line or 'dart::ProfilerService::' in line]
            if unwanted:
                failures.append(f'{mode}/{unit}: ' + '\n'.join(unwanted))
                print('FAIL ' + failures[-1], flush=True)
            else:
                print(f'PASS {mode}/{unit}: no profiler imports', flush=True)
    prefix = 'clang_x64/obj/runtime/vm/libdart_vm_precompiler'
    obj = compile_unit(source, ninja, host, prefix, 'profiler',
                       output / 'host-profiler.o', True)
    symbols = subprocess.check_output([str(nm), '--defined-only', '-C', str(obj)], text=True)
    for method in ('IsolateShutdown', 'IsolateGroupShutdown'):
        if f'dart::Profiler::{method}(' not in symbols:
            failures.append(f'host without Perfetto: missing {method}')
    if failures:
        raise AssertionError('\n'.join(failures))
    print('PASS host lifecycle definitions with Perfetto disabled', flush=True)
    execute_bodies(source, output)


def compile_unit(source, ninja, build, prefix, unit, obj, timeline=None):
    target = f'{prefix}.{unit}.o'
    commands = subprocess.check_output(
        [str(ninja), '-C', str(build), '-t', 'commands', target], text=True)
    command = shlex.split(commands.strip().splitlines()[-1])
    # Keep the actual graph's compiler/ABI/warning flags, but redirect every
    # write and compile the candidate source instead of the evidence checkout.
    for flag in ('-MF', '-o'):
        index = command.index(flag)
        del command[index:index + 2]
    command = [arg for arg in command if arg != '-MMD']
    command = [arg.replace('../../sdk', str(source)) for arg in command]
    if timeline is not None:
        command = [arg for arg in command if arg not in
                   ('-DSUPPORT_PERFETTO', '-DSUPPORT_TIMELINE', '-DDART_DISABLE_TIMELINE')]
        command += ['-DSUPPORT_TIMELINE' if timeline else '-DDART_DISABLE_TIMELINE']
    subprocess.run([*command, '-o', str(obj)], cwd=build, check=True)
    return obj


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'native-aot', 'native-jit', 'host'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path, action='append', default=[])
    args = parser.parse_args()
    if args.source:
        if not all((args.native_aot, args.native_jit, args.host)):
            parser.error('--source requires --native-aot, --native-jit and --host')
        run(args.source, args.native_aot, args.native_jit, args.host, args.output)
    elif not args.archive:
        parser.error('provide --source or at least one --archive')
    check_archives(args.archive, args.output)
