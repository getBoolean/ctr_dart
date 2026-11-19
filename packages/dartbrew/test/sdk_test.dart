import 'dart:io';

import 'package:dartbrew/src/sdk.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

import 'support/fake_sdk.dart';

void main() {
  test('a correctly sealed SDK loads', () async {
    final sdk = await NativeSdk.load(fakeSdk().root.path);
    expect(File(sdk.asset('bin/tool')).readAsStringSync(), payload);
  });

  group('SDK load rejects', () {
    final cases = <String, Directory Function()>{
      'modified asset bytes': () {
        final root = fakeSdk().root;
        File(p.join(root.path, 'bin', 'tool')).writeAsStringSync('tampered');
        return root;
      },
      'a digest that is not lowercase SHA-256': () =>
          fakeSdk(files: {'bin/tool': payloadDigest.toUpperCase()}).root,
      'another native host': () => fakeSdk(host: 'plan9-x64').root,
      'an unknown schema': () => fakeSdk(schema: 2).root,
      'no sealed assets': () => fakeSdk(files: {}).root,
      'an absolute asset path': () =>
          fakeSdk(files: {'/bin/tool': payloadDigest}).root,
      'a backslash asset path': () =>
          fakeSdk(files: {r'bin\tool': payloadDigest}).root,
      'an empty path segment': () =>
          fakeSdk(files: {'bin//tool': payloadDigest}).root,
      'a parent-directory escape': () =>
          fakeSdk(files: {'../owner': '0' * 64}).root,
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
    final outside = Directory.systemTemp.createTempSync('dartbrew-outside-');
    addTearDown(() => outside.deleteSync(recursive: true));
    final target = File(p.join(outside.path, 'tool'))
      ..writeAsStringSync(payload);
    final root = fakeSdk(files: {'bin/link': payloadDigest}).root;
    try {
      Link(p.join(root.path, 'bin', 'link')).createSync(target.path);
    } on FileSystemException {
      markTestSkipped('Host does not permit creating symbolic links.');
      return;
    }
    await expectLater(NativeSdk.load(root.path), throwsFormatException);
  });

  group('quick verification', () {
    test(
      'accepts changed sealed content that full verification rejects',
      () async {
        final root = fakeSdk(tools: {'dart': 0}).root;
        File(p.join(root.path, 'bin', 'tool')).writeAsStringSync('changed');
        final sdk = await NativeSdk.load(root.path, quick: true);
        expect(sdk.tool('dart'), endsWith('dart.dart'));
        await expectLater(NativeSdk.load(root.path), throwsFormatException);
      },
    );

    test('rejects an SDK whose dart tool is missing', () async {
      final root = fakeSdk(tools: {'dart': 0}).root;
      File(p.join(root.path, 'tools', 'dart.dart')).deleteSync();
      await expectLater(
        NativeSdk.load(root.path, quick: true),
        throwsA(
          isA<FileSystemException>().having(
            (e) => e.path,
            'path',
            contains('dart.dart'),
          ),
        ),
      );
    });

    test('still rejects another native host', () async {
      await expectLater(
        NativeSdk.load(
          fakeSdk(host: 'plan9-x64', tools: {'dart': 0}).root.path,
          quick: true,
        ),
        throwsFormatException,
      );
    });
  });
}
