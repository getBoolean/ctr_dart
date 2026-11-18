"""Producer-only dependency closure audit for native SDK executables."""
import struct
from pathlib import Path
from native_binutils import audit_binary

WINDOWS_SYSTEM_DLLS = {
    'kernel32.dll', 'kernelbase.dll', 'user32.dll', 'advapi32.dll', 'shell32.dll',
    'ole32.dll', 'oleaut32.dll', 'ws2_32.dll', 'bcrypt.dll', 'crypt32.dll',
    'rpcrt4.dll', 'ntdll.dll', 'psapi.dll', 'shlwapi.dll', 'dbghelp.dll',
    'version.dll', 'winmm.dll', 'iphlpapi.dll', 'userenv.dll', 'normaliz.dll',
    'secur32.dll', 'msvcrt.dll', 'ucrtbase.dll', 'winhttp.dll', 'dnsapi.dll',
    'powrprof.dll', 'synchronization.dll',
}


def pe_imports(path):
    blob = Path(path).read_bytes()
    pe = struct.unpack_from('<I', blob, 0x3c)[0]
    if blob[:2] != b'MZ' or blob[pe:pe + 4] != b'PE\0\0' or struct.unpack_from('<H', blob, pe + 4)[0] != 0x8664:
        raise ValueError('expected native x64 PE executable')
    optional = pe + 24
    if struct.unpack_from('<H', blob, optional)[0] != 0x20b:
        raise ValueError('expected PE32+ executable')
    sections = optional + struct.unpack_from('<H', blob, pe + 20)[0]
    count = struct.unpack_from('<H', blob, pe + 6)[0]

    def offset(rva):
        for index in range(count):
            at = sections + index * 40
            virtual_size, virtual, size, raw = struct.unpack_from('<IIII', blob, at + 8)
            if virtual <= rva < virtual + max(virtual_size, size):
                result = raw + rva - virtual
                if not raw <= result < raw + size or result >= len(blob):
                    break
                return result
        raise ValueError('PE import RVA outside file-backed sections')

    names = []
    for directory_index, stride, name_offset in [(1, 20, 12), (13, 32, 4)]:
        rva, size = struct.unpack_from('<II', blob, optional + 112 + directory_index * 8)
        if not rva:
            continue
        start = offset(rva)
        for at in range(start, start + size, stride):
            if not any(blob[at:at + stride]):
                break
            if directory_index == 13 and struct.unpack_from('<I', blob, at)[0] != 1:
                raise ValueError('unsupported VA-based delayed import descriptor')
            name = offset(struct.unpack_from('<I', blob, at + name_offset)[0])
            end = blob.index(0, name)
            names.append(blob[name:end].decode('ascii').lower())
    if not names:
        raise ValueError('native PE import table is empty')
    return sorted(set(names))


def audit_sdk(sdk, host, tools):
    sdk = Path(sdk)
    suffix = '.exe' if host.startswith('windows-') else ''
    candidates = {sdk / ('ctr' + suffix), *[sdk / path for path in tools.values()]}
    for path in (sdk / 'host-dart/bin').rglob('*'):
        if path.is_file() and (path.name in {'dart', 'dartvm', 'dartaotruntime', 'dartcliruntime', 'gen_snapshot'} or path.suffix.lower() == '.exe'):
            candidates.add(path)
    results = {}
    pending = list(candidates)
    while pending:
        path = pending.pop()
        relative = path.relative_to(sdk).as_posix()
        if relative in results:
            continue
        if not host.startswith('windows-'):
            results[relative] = audit_binary(path, host)
            continue
        dependencies = pe_imports(path)
        for dependency in dependencies:
            if dependency in WINDOWS_SYSTEM_DLLS or dependency.startswith(('api-ms-win-', 'ext-ms-win-')):
                continue
            companion = path.parent / dependency
            # Windows filenames are case-insensitive on the native producer.
            if not companion.is_file():
                raise ValueError(f'{relative} requires unbundled dependency: {dependency}')
            pending.append(companion)
        results[relative] = dict(dependencies=dependencies)
    return results
