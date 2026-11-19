/// Maps error text from a test run on CTR to the unsupported API area that
/// caused it (KTD10).
///
/// The CTR launcher has no `dart:io` implementation. Its fallback resolver
/// (`runtime/ctr/source/unsupported.cc`) makes every `dart:io` native throw
/// `UnsupportedError: <Native> is not supported on CTR (dart:io)`, so the
/// native's name, plus the stack, identifies the area. The table also keeps
/// the VM's own unresolved-native text, `dart:ffi` and `dart:isolate`
/// failure messages, and `package:test_api`'s `spawnHybridUri` error. The
/// shapes must be confirmed by the device check (U1,
/// `docs/ctr-supported-features.md`).
library;

/// One row of [unsupportedAreas]: an area name and the error text that
/// identifies it.
final class UnsupportedArea {
  /// The area as named in messages, for example `file I/O`.
  final String name;

  /// Matches error text, a stack trace, or the name of an unresolved native.
  final RegExp pattern;

  const UnsupportedArea(this.name, this.pattern);

  /// The failure message that names this area.
  String get message => '$name is not supported on CTR';
}

/// The VM's text for a call into a native that has no resolver, in JIT
/// (`Failed to resolve native function 'File_Open' in '_File._open'`, a
/// fatal error) and with dynamic modules (`native function 'File_Open'
/// (2 arguments) cannot be found`). Group 1 is the native's name.
final unresolvedNative = RegExp(r"native function '([A-Za-z0-9_]+)'");

/// The classification table, checked in order; the first match wins.
///
/// Order matters: `Process_Exit` is exit, not processes, and `IOService_`
/// natives serve both sockets and files, so sockets are checked first.
final List<UnsupportedArea> unsupportedAreas = [
  UnsupportedArea(
    'hybrid tests (spawnHybridUri and spawnHybridCode)',
    RegExp(r'spawnHybrid(Uri|Code)|Can.t connect to the test runner'),
  ),
  UnsupportedArea(
    'stdout, stdin and exit()',
    RegExp(
      r'\b(Process_Exit|Stdout_\w+|Stdin_\w+|File_GetStdioHandleType|'
      r'File_GetStdioHandle|_StdIOUtils)\b',
    ),
  ),
  UnsupportedArea(
    'sockets',
    RegExp(
      r'\b(Socket_\w+|ServerSocket_\w+|RawSocketOption_\w+|'
      r'InternetAddress_\w+|NetworkInterface_\w+|SecureSocket_\w+|'
      r'SecurityContext_\w+|_NativeSocket|_NativeSynchronousSocket|'
      r'_RawSocket|_RawServerSocket|_InternetAddress|_HttpClient)\b',
    ),
  ),
  UnsupportedArea(
    'processes',
    RegExp(r'\b(Process_\w+|_ProcessImpl|ProcessInfo_\w+)\b'),
  ),
  UnsupportedArea(
    'file I/O',
    RegExp(
      r'\b(File_\w+|Directory_\w+|FileSystemWatcher_\w+|IOService_\w+|'
      r'Namespace_\w+|'
      r'_File\.|_Directory\.|_RandomAccessFile|_IOService|_Link\.)',
    ),
  ),
  UnsupportedArea(
    'isolates',
    RegExp(
      r'IsolateSpawnException|Unable to spawn isolate|'
      r'\bIsolate_spawn\w*',
    ),
  ),
  UnsupportedArea(
    'FFI',
    RegExp(
      r'Failed to load dynamic library|Failed to lookup symbol|'
      r'\bFfi_\w+|\bDynamicLibrary\b',
    ),
  ),
  // After the stack-based rows: Process.run and HttpClient reach a
  // Platform_ native first, and their stacks name the real area.
  UnsupportedArea('platform information (Platform)', RegExp(r'\bPlatform_\w+')),
  // Any other native the launcher's dart:io fallback resolver refused.
  UnsupportedArea('dart:io', RegExp(r'is not supported on CTR \(dart:io\)')),
];

/// The area that [text] (an error, a stack trace, or the last output of a
/// run that stopped) names, or null when none is attributable.
UnsupportedArea? classifyUnsupported(String text) {
  for (final area in unsupportedAreas) {
    if (area.pattern.hasMatch(text)) return area;
  }
  return null;
}
