import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:path/path.dart' as p;

String currentHost() {
  final os = Platform.operatingSystem;
  final abi = AbiHost.architecture;
  return '$os-$abi';
}

// Platform.version includes the VM's native architecture even in AOT builds.
abstract final class AbiHost {
  static String get architecture {
    final version = Platform.version;
    if (version.contains('arm64')) return 'arm64';
    if (version.contains('x64')) return 'x64';
    throw UnsupportedError('Unsupported host architecture: $version');
  }
}

Future<String> fileDigest(File file) async =>
    (await sha256.bind(file.openRead()).first).toString();

Map<String, dynamic> objectFile(File file) =>
    jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;

/// The sealed SDK that ships next to the `dartbrew` executable.
class NativeSdk {
  final String root;
  final Map<String, dynamic> manifest;
  NativeSdk._(this.root, this.manifest);

  /// Loads the SDK at [directory] and verifies it.
  ///
  /// Full verification hashes every sealed file. With [quick], only the
  /// manifest schema, the native host and the `dart` tool path are checked,
  /// so commands that forward to the host Dart start without hashing the
  /// whole SDK.
  static Future<NativeSdk> load(String directory, {bool quick = false}) async {
    final root = Directory(directory).resolveSymbolicLinksSync();
    final sdk = NativeSdk._(root, objectFile(File(p.join(root, 'sdk.json'))));
    if (sdk.manifest['schema'] != 1 || sdk.manifest['host'] != currentHost()) {
      throw const FormatException('SDK schema or native host does not match.');
    }
    final files = sdk.manifest['files'] as Map<String, dynamic>;
    if (files.isEmpty) throw const FormatException('SDK has no sealed assets.');
    if (quick) {
      final tools = sdk.manifest['tools'];
      if (tools is! Map || tools['dart'] is! String) {
        throw const FormatException('SDK manifest does not name a dart tool.');
      }
      if (!File(sdk.tool('dart')).existsSync()) {
        throw const FormatException('SDK dart tool is missing.');
      }
      return sdk;
    }
    for (final entry in files.entries) {
      final file = File(sdk.asset(entry.key));
      if (!RegExp(r'^[a-f0-9]{64}$').hasMatch(entry.value as String) ||
          await fileDigest(file) != entry.value) {
        throw FormatException('SDK asset hash mismatch: ${entry.key}');
      }
    }
    return sdk;
  }

  String asset(String relative) {
    if (p.posix.isAbsolute(relative) ||
        relative.contains('\\') ||
        relative.split('/').any((part) => part == '..' || part.isEmpty) ||
        !(manifest['files'] as Map<String, dynamic>).containsKey(relative)) {
      throw FormatException('Invalid SDK asset path: $relative');
    }
    final file = File(p.joinAll([root, ...relative.split('/')]));
    final resolved = file.resolveSymbolicLinksSync();
    if (!p.isWithin(root, resolved)) {
      throw FormatException('SDK asset escapes its directory: $relative');
    }
    return resolved;
  }

  Map<String, dynamic> get runtime =>
      manifest['runtime'] as Map<String, dynamic>;
  String tool(String name) =>
      asset((manifest['tools'] as Map<String, dynamic>)[name] as String);
}
