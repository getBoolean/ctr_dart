import 'dart:ffi';
import 'dart:io';
import 'package:ffi/ffi.dart';
import 'package:path/path.dart' as p;

/// Reserve a build directory with one OS operation that rejects existing paths.
/// Dart's Directory.create treats an existing directory as success.
void createDirectoryExclusively(String path) {
  if (path.contains('\u0000')) {
    throw FileSystemException('Invalid directory path', path);
  }
  final bool created;
  if (Platform.isWindows) {
    final create = DynamicLibrary.open('kernel32.dll')
        .lookupFunction<
          Int32 Function(Pointer<Utf16>, Pointer<Void>),
          int Function(Pointer<Utf16>, Pointer<Void>)
        >('CreateDirectoryW');
    var nativePath = Directory(path).absolute.path.replaceAll('/', '\\');
    if (!nativePath.startsWith(r'\\?\')) {
      // The \\?\ prefix disables Win32 '.' and '..' handling; resolve them first.
      nativePath = p.windows.normalize(nativePath);
      nativePath = nativePath.startsWith(r'\\')
          ? r'\\?\UNC\' + nativePath.substring(2)
          : r'\\?\' + nativePath;
    }
    final native = nativePath.toNativeUtf16();
    try {
      created = create(native, nullptr) != 0;
    } finally {
      malloc.free(native);
    }
  } else if (Platform.isLinux || Platform.isMacOS) {
    final native = path.toNativeUtf8();
    try {
      final library = DynamicLibrary.process();
      // Darwin mode_t is uint16_t; Linux mode_t is unsigned int.
      if (Platform.isMacOS) {
        final create = library
            .lookupFunction<
              Int32 Function(Pointer<Utf8>, Uint16),
              int Function(Pointer<Utf8>, int)
            >('mkdir');
        created = create(native, 0x1ff) == 0;
      } else {
        final create = library
            .lookupFunction<
              Int32 Function(Pointer<Utf8>, Uint32),
              int Function(Pointer<Utf8>, int)
            >('mkdir');
        created = create(native, 0x1ff) == 0;
      }
    } finally {
      malloc.free(native);
    }
  } else {
    throw UnsupportedError('Unsupported SDK host: ${Platform.operatingSystem}');
  }
  if (!created) {
    throw FileSystemException(
      'OS rejected exclusive directory creation; '
      'the output may already exist or be unwritable',
      path,
    );
  }
}
