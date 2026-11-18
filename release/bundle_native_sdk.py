"""Producer-only assembly of a complete native SDK from verified components."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def checked(root, name, expected):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or digest(path) != expected:
        raise ValueError(f'component path or hash mismatch: {name}')
    return path


def assemble(cli, precompiler, binutils, runtime, output, version):
    cli, precompiler, binutils, runtime, output = map(Path, (cli, precompiler, binutils, runtime, output))
    if output.exists():
        raise ValueError('SDK output already exists; choose a fresh directory')
    host = read(precompiler / 'native-precompiler.json')
    arm = read(binutils / 'provenance.json')
    target = read(runtime / 'runtime.json')
    if host['host'] != arm['host'] or host['source']['head'] != target['sdk_head']:
        raise ValueError('component host or SDK identity mismatch')
    if target['program_size'] != 32 or target['program_identity_offset'] != 16:
        raise ValueError('unsupported target Program ABI')
    if host['generated']['git_short_hash'] != target['sdk_head'][:10]:
        raise ValueError('precompiler SDK hash mismatch')
    if host['generated']['snapshot_hash'] != target['snapshot_hash']:
        raise ValueError('precompiler/runtime snapshot hash mismatch')
    inputs = []
    suffix = '.exe' if host['host'].startswith('windows-') else ''
    tools = {}
    for key, field, name in [('snapshot', 'executable', 'gen_snapshot'), ('kernel', 'kernel_compiler', 'ctr-kernel')]:
        record = host[field]
        tools[key] = f'bin/{name}{suffix}'
        inputs.append((checked(precompiler, record['path'], record['sha256']), tools[key], True))
    for name in ('ctr-as', 'ctr-ld'):
        filename = name + suffix
        record = arm['tools'][filename]
        tools['as' if name == 'ctr-as' else 'ld'] = 'bin/' + filename
        inputs.append((checked(binutils, 'bin/' + filename, record['sha256']), 'bin/' + filename, True))
    for name, record in host['host_dart'].items():
        if name.startswith('bin/') and (name.endswith('.sym') or
                Path(name).stem.endswith(('_asan', '_msan', '_tsan'))):
            continue
        inputs.append((checked(precompiler / 'host-dart', name, record['sha256']),
                       'host-dart/' + name, record['executable']))
    tools['dart'] = 'host-dart/bin/dart' + suffix
    for name, sha in target['files'].items():
        inputs.append((checked(runtime, name, sha), name, False))
    if not cli.is_file():
        raise ValueError('compiled CLI is missing')
    source_asset = output.parent / f'source-ctr-binutils-{version}-{host["host"]}.zip'
    checked(binutils / 'source', arm['source']['archive'], arm['source']['sha256'])
    archive_sdk(binutils / 'source', source_asset)
    inputs.append((cli, 'ctr' + suffix, True))
    output.mkdir(parents=True)
    for source, name, executable in inputs:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o755 if executable else 0o644)
    notices = output / 'notices'
    notices.mkdir()
    for name in ['LICENSE', 'CREDITS.md', *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT / 'release/licenses').glob('*')) if p.is_file()]]:
        shutil.copyfile(ROOT / name, notices / Path(name).name)
    shutil.copytree(binutils / 'licenses', notices / 'binutils')
    shutil.copyfile(binutils / 'NOTICE.txt', notices / 'binutils-NOTICE.txt')
    (notices / 'binutils-source-location.txt').write_text(
        f'Corresponding source and controlling build material accompany this SDK as {source_asset.name}.\n'
        f'SHA256: {digest(source_asset)}\n'
        'Retain that source asset with redistributed copies of the GNU binaries.\n', encoding='utf-8')
    shutil.copytree(ROOT / 'release/target-sources', notices / 'target-sources')
    provenance = output / 'provenance'
    provenance.mkdir()
    for source, name in [(precompiler / 'native-precompiler.json', 'host.json'),
                         (binutils / 'provenance.json', 'binutils.json'),
                         (runtime / 'runtime.json', 'runtime.json')]:
        shutil.copyfile(source, provenance / name)
    (output / 'README.txt').write_text(
        'CTR Dart native SDK (experimental New 3DS runtime)\n'
        'Run ctr doctor, then ctr build path/to/main.dart --mode aot --output fresh-directory.\n'
        'Windows: use .\\ctr.exe. macOS/Linux: use ./ctr.\n'
        'All build tools and target libraries are bundled. No Docker or separately installed compiler is required.\n'
        'Pub dependencies need network access on first resolution, or a populated cache with --offline.\n'
        'Copy SDROOT contents to your SD card and launch the application through Homebrew Launcher.\n'
        'File/network I/O, application isolates, FFI and Flutter are not qualified by this preview.\n', encoding='utf-8')
    executable_paths = [name for _, name, executable in inputs if executable]
    files = {path.relative_to(output).as_posix(): digest(path)
             for path in sorted(output.rglob('*')) if path.is_file()}
    manifest = dict(schema=1, version=version, host=host['host'], tools=tools,
                    runtime={key: target[key] for key in ['sdk_head', 'platform', 'modes', 'link']},
                    snapshot_hash=host['generated']['snapshot_hash'], files=files,
                    corresponding_source=dict(asset=source_asset.name, sha256=digest(source_asset)),
                    executable_paths=executable_paths)
    (output / 'sdk.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def archive_sdk(directory, output):
    """Keep executable modes in the distribution ZIP (Actions artifacts lose them)."""
    directory, output = Path(directory), Path(output)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                archive.write(path, directory.name + '/' + path.relative_to(directory).as_posix())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['cli', 'precompiler', 'binutils', 'runtime', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    assemble(args.cli, args.precompiler, args.binutils, args.runtime, args.output, args.version)
    archive_sdk(args.output, args.output.with_suffix('.zip'))
