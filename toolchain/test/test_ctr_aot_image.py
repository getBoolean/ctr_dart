"""Generate and assemble a real CTR AOT image; this does not execute Dart on CTR."""
import argparse
import json
from pathlib import Path
import subprocess


def run(precompiler, kernel, output):
    output.mkdir(parents=True, exist_ok=False)
    profile = json.loads((Path(__file__).parents[1] / 'target-ctr.json').read_text())
    for name, flags in (('debug', []), ('stripped', ['--strip'])):
        assembly = output / (name + '.S')
        subprocess.run([str(precompiler), '--snapshot_kind=app-aot-assembly',
                        '--assembly=' + str(assembly), '--add-readonly-data-symbols',
                        *flags, str(kernel)], check=True, timeout=180)
        obj = assembly.with_suffix('.o')
        subprocess.run([profile['compiler_prefix'] + 'gcc', *profile['cflags'],
                        '-c', str(assembly), '-o', str(obj)], check=True, timeout=60)
        header = subprocess.check_output([
            profile['compiler_prefix'] + 'readelf', '-h', str(obj)], text=True)
        assert 'ELF32' in header and 'ARM' in header
        symbols = subprocess.check_output([
            profile['compiler_prefix'] + 'readelf', '-sW', str(obj)], text=True)
        for symbol in ('_kDartSnapshotData', '_kDartSnapshotText'):
            row = next(line.split() for line in symbols.splitlines()
                       if line.split() and line.split()[-1] == symbol)
            assert int(row[2], 0) > 0 and row[3] == 'OBJECT' and row[6] != 'UND', row
        sections = subprocess.check_output([
            profile['compiler_prefix'] + 'readelf', '-SW', str(obj)], text=True)
        assert '.note.GNU-stack' in sections
        for section in ('.debug_info', '.debug_abbrev', '.debug_line'):
            assert (section in sections) == (name == 'debug'), (name, section)
        print('PASS CTR AOT generation and native ELF assembly: ' + name, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('precompiler', 'kernel', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.precompiler.resolve(), args.kernel.resolve(), args.output.resolve())
