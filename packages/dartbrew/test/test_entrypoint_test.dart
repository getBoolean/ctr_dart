import 'dart:io';

import 'package:dartbrew/src/targets/ctr/test_entrypoint.dart';
import 'package:dartbrew/src/test_runner/reporter.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

String _tempProject() {
  final root = Directory.systemTemp.createTempSync('dartbrew-entry-');
  addTearDown(() => root.deleteSync(recursive: true));
  return root.resolveSymbolicLinksSync();
}

void _write(String project, String path, String contents) =>
    File(p.join(project, path))
      ..createSync(recursive: true)
      ..writeAsStringSync(contents);

/// The resolved `test` version the generated entrypoint is checked against.
const _testVersion = '1.33.0';

const _noCache =
    'package:test $_testVersion is not in the pub cache; run '
    '"dart pub cache add test --version $_testVersion" to enable this test.';

void main() {
  test('two files are imported under unique prefixes, filters are baked in '
      'and dart:io is not used', () {
    final project = _tempProject();
    final entry = writeTestEntrypoint(
      project: project,
      testFiles: [
        p.join(project, 'test', 'a_test.dart'),
        p.join(project, 'test', 'nested', 'b_test.dart'),
      ],
      names: ['parse'],
      plainNames: [r'a $b'],
      firstId: 3,
    );

    expect(
      entry.path,
      p.join(project, '.dart_tool', 'dartbrew', 'test', 'dartbrew_test.dart'),
    );
    final source = entry.readAsStringSync();
    expect(source, contains("import \"../../../test/a_test.dart\" as t0;"));
    expect(
      source,
      contains("import \"../../../test/nested/b_test.dart\" as t1;"),
    );
    expect(source, contains('"test/nested/b_test.dart",'));
    expect(source, contains('RegExp("parse"),'));
    expect(source, contains(r'"a \$b",'));
    expect(source, contains('int _nextId = 3;'));
    expect(source, isNot(contains('dart:io')));
  });

  test('resolvedTestApiVersion reads pubspec.lock, then package_config', () {
    final project = _tempProject();
    expect(resolvedTestApiVersion(project), isNull);
    _write(project, '.dart_tool/package_config.json', '''
{"configVersion": 2, "packages": [
  {"name": "test_api", "rootUri": "file:///cache/hosted/pub.dev/test_api-0.7.14", "packageUri": "lib/"}
]}''');
    expect(resolvedTestApiVersion(project), '0.7.14');
    _write(project, 'pubspec.lock', '''
packages:
  test:
    dependency: "direct dev"
    description:
      name: test
    source: hosted
    version: "1.40.0"
  test_api:
    dependency: transitive
    description:
      name: test_api
      url: "https://pub.dev"
    source: hosted
    version: "0.8.1"
''');
    expect(resolvedTestApiVersion(project), '0.8.1');
    expect(isTestedTestApi('0.8.1'), isFalse);
    expect(isTestedTestApi('0.7.15'), isTrue);
    expect(isTestedTestApi('0.70.0'), isFalse);
  });

  group('against a project resolving test $_testVersion', () {
    late String project;
    final dart = Platform.resolvedExecutable;

    setUpAll(() async {
      final root = Directory.systemTemp.createTempSync('dartbrew-entry-');
      project = root.resolveSymbolicLinksSync();
      _write(project, 'pubspec.yaml', '''
name: sample
environment:
  sdk: '>=3.0.0 <4.0.0'
dev_dependencies:
  test: $_testVersion
''');
      _write(project, 'test/parse_test.dart', '''
import 'package:test/test.dart';

void main() {
  group('parse', () {
    test('an int', () => expect(int.parse('7'), 7));
    test('fails', () {
      print('about to fail');
      expect(int.parse('7'), 8);
    });
  });
  test('skipped', () {}, skip: 'not today');
}
''');
      _write(project, 'test/other_test.dart', '''
import 'package:test/test.dart';

void main() {
  test('adds', () async {
    await Future<void>.delayed(const Duration(milliseconds: 1));
    expect(1 + 1, 2);
  });
  test('hybrid', () => spawnHybridUri('hybrid.dart'));
}
''');
      final get = await Process.run(dart, [
        'pub',
        'get',
        '--offline',
      ], workingDirectory: project);
      if (get.exitCode != 0) {
        markTestSkipped('$_noCache\n${get.stderr}');
        root.deleteSync(recursive: true);
        project = '';
      }
    });
    tearDownAll(() {
      if (project.isNotEmpty) Directory(project).deleteSync(recursive: true);
    });

    List<String> files() => [
      p.join(project, 'test', 'other_test.dart'),
      p.join(project, 'test', 'parse_test.dart'),
    ];

    /// Runs the entrypoint on the host VM and renders its output.
    Future<({int code, String report})> runOnHost() async {
      final run = await Process.run(dart, [
        'run',
        p.join('.dart_tool', 'dartbrew', 'test', 'dartbrew_test.dart'),
      ], workingDirectory: project);
      expect(run.exitCode, 0, reason: '${run.stdout}\n${run.stderr}');
      final out = StringBuffer();
      final session = TestSession(
        CompactRenderer(out),
        elapsed: () => Duration.zero,
      )..begin(2);
      session.addOutput(run.stdout as String);
      expect(session.deviceDone, isTrue);
      return (code: session.finish(), report: out.toString());
    }

    test('the generated entrypoint passes dart analyze', () async {
      if (project.isEmpty) return markTestSkipped(_noCache);
      final entry = writeTestEntrypoint(project: project, testFiles: files());
      final analyze = await Process.run(dart, [
        'analyze',
        '--fatal-infos',
        entry.path,
      ], workingDirectory: project);
      expect(
        analyze.exitCode,
        0,
        reason: '${analyze.stdout}\n${analyze.stderr}',
      );
      expect(resolvedTestApiVersion(project), '0.7.15');
    });

    test('run on the host, it reports every test as events', () async {
      if (project.isEmpty) return markTestSkipped(_noCache);
      writeTestEntrypoint(project: project, testFiles: files());
      final r = await runOnHost();
      printOnFailure(r.report);

      expect(r.code, 1);
      expect(r.report, contains('test/other_test.dart: adds'));
      expect(
        r.report,
        contains(
          'test/other_test.dart: hybrid [E]\n'
          '  hybrid tests (spawnHybridUri and spawnHybridCode) is not '
          'supported on CTR.',
        ),
      );
      expect(r.report, contains('about to fail\n'));
      expect(r.report, contains('test/parse_test.dart: parse fails [E]'));
      expect(r.report, contains('Expected: <8>'));
      expect(r.report, endsWith('+2 ~1 -2: Some tests failed.\n'));
    });

    test('--name parse bakes the filter in: only matching tests run', () async {
      if (project.isEmpty) return markTestSkipped(_noCache);
      writeTestEntrypoint(
        project: project,
        testFiles: files(),
        names: ['parse'],
        plainNames: ['an int'],
      );
      final r = await runOnHost();

      expect(r.code, 0, reason: r.report);
      expect(r.report, contains('test/parse_test.dart: parse an int'));
      expect(r.report, isNot(contains('adds')));
      expect(r.report, isNot(contains('fails')));
      expect(r.report, endsWith('+1: All tests passed!\n'));
    });
  }, timeout: const Timeout(Duration(minutes: 3)));
}
