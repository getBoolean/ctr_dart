import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:dartbrew/src/sdk.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

const payload = 'sealed tool bytes';
final payloadDigest = sha256.convert(utf8.encode(payload)).toString();

/// A temporary SDK for tests. Deleted when the current test ends.
class FakeSdk {
  final Directory root;
  FakeSdk._(this.root);

  /// Every argument list the stub for [tool] was started with, in order.
  List<List<String>> calls(String tool) {
    final log = File(p.join(root.path, 'calls', '$tool.json'));
    if (!log.existsSync()) return [];
    return [
      for (final call in jsonDecode(log.readAsStringSync()) as List<dynamic>)
        (call as List<dynamic>).cast<String>(),
    ];
  }
}

/// Writes a minimal SDK with one sealed asset, `bin/tool`.
///
/// Each entry in [tools] adds a sealed stub executable at `tools/<name>.dart`
/// and maps the manifest's `tools.<name>` to it. A stub records its
/// arguments (see [FakeSdk.calls]), writes `<name> stdout` and
/// `<name> stderr`, and exits with the given code. Start stubs with
/// [startStub].
///
/// [files] replaces the generated `files` map as-is.
FakeSdk fakeSdk({
  Object? schema = 1,
  String? host,
  Map<String, String>? files,
  Map<String, int> tools = const {},
}) {
  final root = Directory.systemTemp.createTempSync('dartbrew-sdk-test-');
  addTearDown(() => root.deleteSync(recursive: true));
  final sealed = <String, String>{};
  void seal(String relative, String contents) {
    final file = File(p.joinAll([root.path, ...relative.split('/')]));
    file.parent.createSync(recursive: true);
    file.writeAsStringSync(contents);
    sealed[relative] = sha256.convert(utf8.encode(contents)).toString();
  }

  seal('bin/tool', payload);
  final calls = Directory(p.join(root.path, 'calls'))..createSync();
  for (final MapEntry(key: name, value: code) in tools.entries) {
    final log = p.join(calls.path, '$name.json');
    seal('tools/$name.dart', '''
import 'dart:convert';
import 'dart:io';

void main(List<String> arguments) {
  final log = File(${jsonEncode(log)});
  final calls = log.existsSync() ? jsonDecode(log.readAsStringSync()) as List : [];
  log.writeAsStringSync(jsonEncode([...calls, arguments]));
  stdout.writeln('$name stdout');
  stderr.writeln('$name stderr');
  exitCode = $code;
}
''');
  }
  File(p.join(root.path, 'sdk.json')).writeAsStringSync(
    jsonEncode({
      'schema': schema,
      'host': host ?? currentHost(),
      'files': files ?? sealed,
      'tools': {for (final name in tools.keys) name: 'tools/$name.dart'},
    }),
  );
  return FakeSdk._(root);
}

/// A process starter that runs fake SDK stubs with the current Dart VM.
Future<Process> startStub(
  String executable,
  List<String> arguments, {
  String? workingDirectory,
  Map<String, String>? environment,
  ProcessStartMode mode = ProcessStartMode.normal,
}) => Process.start(
  Platform.resolvedExecutable,
  [executable, ...arguments],
  workingDirectory: workingDirectory,
  environment: environment,
  mode: mode,
);
