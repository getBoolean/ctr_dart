"""Producer-only runtime asset archive for native SDK assembly jobs."""
import argparse
import json
from pathlib import Path
import subprocess
import zipfile

from bundle_native_sdk import ROOT, checked, digest, read


def archive_runtime(runtime, output, probe_kernel, precompiler):
    runtime, output = Path(runtime), Path(output)
    record = read(runtime / 'runtime.json')
    files = [(runtime / 'runtime.json', 'runtime.json')]
    for name, sha in record['files'].items():
        files.append((checked(runtime, name, sha), name))
    for directory in ['release/licenses', 'release/target-sources']:
        for path in sorted((ROOT / directory).rglob('*')):
            if path.is_file():
                files.append((path, 'notices/' + path.relative_to(ROOT / 'release').as_posix()))
    assembly = output.with_suffix('.reference.S')
    subprocess.run([str(precompiler), '--snapshot_kind=app-aot-assembly',
                    '--assembly=' + str(assembly), str(probe_kernel)], check=True)
    probe = dict(kernel='probe.dill', kernel_sha256=digest(probe_kernel),
                 assembly_sha256=digest(assembly),
                 reference_precompiler_sha256=digest(precompiler))
    probe_file = output.with_suffix('.probe.json')
    probe_file.write_text(json.dumps(probe, indent=2) + '\n')
    files.extend([(Path(probe_kernel), 'probe.dill'), (probe_file, 'probe.json')])
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path, name in files:
            archive.write(path, name)
    result = dict(sha256=digest(output),
                  sdk_head=record['sdk_head'], snapshot_hash=record['snapshot_hash'])
    output.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--probe-kernel', type=Path, required=True)
    parser.add_argument('--precompiler', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(archive_runtime(args.runtime, args.output, args.probe_kernel, args.precompiler)))
