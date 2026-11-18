import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:ctr_dart/src/native_sdk.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

const _payload = 'sealed tool bytes';
final _payloadDigest = sha256.convert(utf8.encode(_payload)).toString();

/// Writes a minimal SDK with one sealed asset and returns its root.
Directory _sdk({Object? schema = 1, String? host, Map<String, String>? files}) {
  final root = Directory.systemTemp.createTempSync('ctr-sdk-test-');
  addTearDown(() => root.deleteSync(recursive: true));
  Directory(p.join(root.path, 'bin')).createSync();
  File(p.join(root.path, 'bin', 'tool')).writeAsStringSync(_payload);
  File(p.join(root.path, 'sdk.json')).writeAsStringSync(
    jsonEncode({
      'schema': schema,
      'host': host ?? currentHost(),
      'files': files ?? {'bin/tool': _payloadDigest},
    }),
  );
  return root;
}

void main() {
  test('a correctly sealed SDK loads', () async {
    final sdk = await NativeSdk.load(_sdk().path);
    expect(File(sdk.asset('bin/tool')).readAsStringSync(), _payload);
  });

  group('SDK load rejects', () {
    final cases = <String, Directory Function()>{
      'modified asset bytes': () {
        final root = _sdk();
        File(p.join(root.path, 'bin', 'tool')).writeAsStringSync('tampered');
        return root;
      },
      'a digest that is not lowercase SHA-256': () =>
          _sdk(files: {'bin/tool': _payloadDigest.toUpperCase()}),
      'another native host': () => _sdk(host: 'plan9-x64'),
      'an unknown schema': () => _sdk(schema: 2),
      'no sealed assets': () => _sdk(files: {}),
      'an absolute asset path': () =>
          _sdk(files: {'/bin/tool': _payloadDigest}),
      'a backslash asset path': () =>
          _sdk(files: {r'bin\tool': _payloadDigest}),
      'an empty path segment': () => _sdk(files: {'bin//tool': _payloadDigest}),
      'a parent-directory escape': () => _sdk(files: {'../owner': '0' * 64}),
    };
    for (final entry in cases.entries) {
      test(entry.key, () async {
        await expectLater(
          NativeSdk.load(entry.value().path),
          throwsFormatException,
        );
      });
    }
  });

  test('SDK load rejects an asset symlink that leaves the SDK', () async {
    final outside = Directory.systemTemp.createTempSync('ctr-sdk-outside-');
    addTearDown(() => outside.deleteSync(recursive: true));
    final target = File(p.join(outside.path, 'tool'))
      ..writeAsStringSync(_payload);
    final root = _sdk(files: {'bin/link': _payloadDigest});
    try {
      Link(p.join(root.path, 'bin', 'link')).createSync(target.path);
    } on FileSystemException {
      markTestSkipped('Host does not permit creating symbolic links.');
      return;
    }
    await expectLater(NativeSdk.load(root.path), throwsFormatException);
  });

  test('metadata assembly has exactly the native Program fields', () {
    final assembly = programAssembly('jit', 'app', 'a' * 64, 'b' * 64, 123);
    expect(assembly, contains('.word 0, 0, ctr_kernel, 123'));
    expect(assembly, contains('.size ctr_program, 32'));
    expect(
      assembly,
      contains('.word ctr_fixture, ctr_mode, ctr_compatibility, ctr_build_id'),
    );
  });
}
