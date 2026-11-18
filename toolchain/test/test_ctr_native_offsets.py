"""Compare actual native CTR scalar layouts with the compiler's target constants."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DEFAULT_MANIFEST, DEFAULT_PROFILE, read_json, verify_source


INCLUDES = ('compiler/runtime_api.h', 'compiler/runtime_offsets_list.h',
            'dart_api_state.h', 'dart_entry.h', 'longjump.h', 'native_arguments.h',
            'native_entry.h', 'object.h', 'object_store.h', 'runtime_entry.h',
            'symbols.h', 'timeline.h')
EXTRACT = r'''
#define FIELD(C,N) asm volatile(".global ctr_" #C "_" #N "\n.set ctr_" #C "_" #N ", %c0" : : "i"(C::N()));
#define ARRAY(C,N)
#define SIZE(C,N,W) asm volatile(".global ctr_" #C "_" #N "\n.set ctr_" #C "_" #N ", %c0" : : "i"(sizeof(W)));
#define IGNORE3(C,N,W)
#define IGNORE7(C,N,T,F,L,I)
#define CONSTANT(C,N) asm volatile(".global ctr_" #C "_" #N "\n.set ctr_" #C "_" #N ", %c0" : : "i"(C::N));
#define ENUM(N,E)
namespace dart { class OffsetsExtractor { public: static void DumpOffsets() {
MODE_OFFSETS_LIST(FIELD, ARRAY, SIZE, IGNORE3, IGNORE3, IGNORE7, CONSTANT, ENUM)
COMMON_OFFSETS_LIST(FIELD, ARRAY, SIZE, IGNORE3, IGNORE3, IGNORE7, CONSTANT, ENUM)
} }; }
extern "C" void extract() { dart::OffsetsExtractor::DumpOffsets(); }
'''


def run(source, build, mode, output, header=None):
    source, build = source.resolve(), build.resolve()
    state = verify_source(source, read_json(DEFAULT_MANIFEST))
    profile = read_json(DEFAULT_PROFILE)
    output.mkdir(parents=True, exist_ok=False)
    kind = 'aotruntime' if mode == 'aot' else 'jit'
    target = f'obj/runtime/vm/libdart_vm_{kind}.os_thread_ctr.o'
    commands = subprocess.check_output([
        str(source / 'buildtools/ninja/ninja'), '-C', str(build), '-t', 'commands', target], text=True)
    command = shlex.split(commands.strip().splitlines()[-1])
    if command[0] != profile['compiler_prefix'] + 'g++':
        raise AssertionError('native layout check requires the configured devkitARM compiler')
    for flag in ('-MF', '-o', '-c'):
        index = command.index(flag)
        del command[index:index + 2]
    command = [arg.replace('../../sdk', str(source)) for arg in command if arg != '-MMD']
    if ('-DDART_PRECOMPILED_RUNTIME' in command) != (mode == 'aot'):
        raise AssertionError('runtime build profile differs from requested mode')
    (output / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    extract = output / 'extract.cc'
    extract.write_text(''.join(f'#include "vm/{name}"\n' for name in INCLUDES) +
                       EXTRACT.replace('MODE_OFFSETS_LIST', mode.upper() + '_OFFSETS_LIST'))
    obj = output / 'values.o'
    subprocess.run([*command, '-c', str(extract), '-o', str(obj)], cwd=build, check=True)
    symbols = subprocess.check_output([profile['compiler_prefix'] + 'nm', str(obj)], text=True)
    actual = {name[4:]: int(value, 16) for value, name in re.findall(
        r'^([0-9a-f]+) A (ctr_\w+)$', symbols, re.M)}
    if len(actual) < 400:
        raise AssertionError('native scalar extraction is incomplete')
    header = (header or source / 'runtime/vm/compiler/runtime_offsets_extracted.h').resolve()
    constants_source = output / 'constants.cc'
    constants_source.write_text('#include "vm/compiler/runtime_api.h"\n' +
                                '#include "' + str(header) + '"\n')
    preprocessed = subprocess.check_output([
        *command, '-E', '-P', str(constants_source)], cwd=build, text=True)
    constants = {name: int(value, 0) & 0xffffffff for name, value in re.findall(
        r'static constexpr dart::compiler::target::word\s+(\w+)\s*=\s*'
        r'(-?(?:0x[0-9a-f]+|[0-9]+));', preprocessed)}
    if len(constants) < 400:
        raise AssertionError('compiler target constants were not extracted')
    differences = {}
    for name, value in actual.items():
        expected = constants.get(('AOT_' if mode == 'aot' else '') + name,
                                 constants.get(name))
        if value != expected:
            differences[name] = {'actual': value, 'generated': expected}
    result = {'mode': mode, 'source_head': state['head'], 'header': str(header),
              'count': len(actual), 'differences': differences}
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    if differences:
        raise AssertionError(f'{len(differences)} native layout mismatches; see {output / "result.json"}')
    print(f'PASS {mode}: {len(actual)} actual native scalar constants, zero mismatches')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--mode', choices=('aot', 'jit'), required=True)
    parser.add_argument('--output', type=Path, required=True, help='new evidence directory')
    parser.add_argument('--header', type=Path, help='alternate constants header for negative controls')
    args = parser.parse_args()
    run(args.source, args.build, args.mode, args.output.resolve(), args.header)
