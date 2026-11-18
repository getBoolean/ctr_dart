"""Compare checked-in compiler offsets with the actual VM layout extractor."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile


def run(source, header, all_configs):
    sections = re.split(r'(?=\n#if )', header.read_text())[1:]
    compiler = source / 'buildtools/linux-x64/clang/bin/clang++'
    checked = 0
    configurations = 0
    with tempfile.TemporaryDirectory(prefix='ctr-offsets-') as directory:
        for index, section in enumerate(sections):
            condition = section.split('\nstatic', 1)[0]
            arch = re.search(r'TARGET_ARCH_(\w+)', condition).group(1)
            if not all_configs and arch != 'X64':
                continue
            # Upstream emits all JIT sections before the AOT sections. IA32 AOT
            # is empty, so it cannot be identified by searching for an AOT field.
            aot = index >= len(sections) // 2
            bits = 32 if arch in ('ARM', 'IA32', 'RISCV32') else 64
            flags = ['-std=c++20', '-O2', '-DDART_DISABLE_TIMELINE',
                     '-DTARGET_ARCH_' + arch, '-DDART_HOST_OS_LINUX',
                     '-DDART_TARGET_OS_LINUX', '-I' + str(source / 'runtime'),
                     '-m' + str(bits),
                     '-DHOST_ARCH_' + ('IA32' if bits == 32 else 'X64')]
            if '!defined(PRODUCT)' not in condition:
                flags.append('-DPRODUCT')
            if '!defined(DART_COMPRESSED_POINTERS)' not in condition:
                flags.append('-DDART_COMPRESSED_POINTERS')
            if aot:
                flags.append('-DDART_PRECOMPILED_RUNTIME')
            binary = Path(directory) / f'extractor-{index}'
            subprocess.run([str(compiler), *flags,
                            str(source / 'runtime/vm/compiler/offsets_extractor.cc'),
                            '-o', str(binary)], check=True)
            actual = json.loads(subprocess.check_output([str(binary)], text=True))
            constants = {key: int(value, 0) for key, value in re.findall(
                r'word\s+(\w+)\s*=\s*(-?0x[\da-f]+|-?\d+)\s*;', section)}
            differences = []
            for entry in actual['offsets']:
                if entry.get('kind') != 'value':
                    continue
                key = ('AOT_' if aot else '') + entry['class'] + '_' + entry['name']
                observed = int(entry['value'])
                if constants.get(key) != observed:
                    differences.append(f'{key}: header={constants.get(key)}, VM={observed}')
                checked += 1
            if differences:
                raise RuntimeError(f'VM layout mismatch in configuration {index}:\n' +
                                   '\n'.join(differences))
            configurations += 1
            print(f'PASS offsets: {arch}, AOT={aot}, configuration={index}', flush=True)
    if not checked or not configurations:
        raise RuntimeError('No VM layout values were checked')
    print(f'PASS {checked} scalar values in {configurations} configurations')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--header', type=Path,
                        help='check an exported replacement header before source replay')
    parser.add_argument('--all', action='store_true', dest='all_configs',
                        help='also extract non-host profiles; requires 32-bit C++ libraries')
    args = parser.parse_args()
    run(args.source, args.header or args.source /
        'runtime/vm/compiler/runtime_offsets_extracted.h', args.all_configs)
