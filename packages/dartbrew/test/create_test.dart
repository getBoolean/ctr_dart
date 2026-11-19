import 'dart:io';

import 'package:args/command_runner.dart';
import 'package:dartbrew/src/commands/create.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

import 'support/fake_sdk.dart';

class Created {
  final int? code;
  final Directory root;
  final FakeSdk sdk;
  final List<String?> workingDirectories;
  Created(this.code, this.root, this.sdk, this.workingDirectories);
  File file(String relative) => File(p.join(root.path, relative));
}

Future<Created> create(
  List<String> args, {
  String name = 'snake',
  void Function(Directory)? prepare,
}) async {
  final sdk = fakeSdk(tools: {'dart': 0});
  final parent = Directory.systemTemp.createTempSync('dartbrew-create-test-');
  addTearDown(() => parent.deleteSync(recursive: true));
  final root = Directory(p.join(parent.path, name));
  if (prepare != null) {
    root.createSync();
    prepare(root);
  }
  final directories = <String?>[];
  final runner = CommandRunner<int>('dartbrew', 'test')
    ..addCommand(
      createCommand(
        sdkDir: () => sdk.root.path,
        start:
            (
              exe,
              args, {
              workingDirectory,
              environment,
              mode = ProcessStartMode.normal,
            }) {
              directories.add(workingDirectory);
              return startStub(exe, args);
            },
      ),
    );
  final code = await runner.run(['create', ...args, root.path]);
  return Created(code, root, sdk, directories);
}

void main() {
  test('writes the project files with the directory name as package', () async {
    final r = await create(['--no-pub']);
    expect(r.code, 0);
    for (final path in [
      'pubspec.yaml',
      'bin/main.dart',
      'lib/snake.dart',
      'test/snake_test.dart',
      'analysis_options.yaml',
      'README.md',
      '.gitignore',
    ]) {
      expect(r.file(path).existsSync(), isTrue, reason: path);
    }
    final pubspec = r.file('pubspec.yaml').readAsStringSync();
    expect(pubspec, contains('name: snake\n'));
    expect(pubspec, contains('title: snake\n'));
    expect(pubspec, contains('# icon: assets/icon.png'));
    final readme = r.file('README.md').readAsStringSync();
    for (final word in [
      'dartbrew compile',
      'dartbrew run',
      'dartbrew test',
      'dartbrew devices',
      'dart test',
      'press Y',
    ]) {
      expect(readme, contains(word));
    }
    expect(readme, isNot(contains('3DS')));
  });

  for (final name in ['Snake', '1snake', 'my-app', 'class', 'a b']) {
    test('invalid name "$name" exits 64 without writing', () async {
      final sdk = fakeSdk(tools: {'dart': 0});
      final parent = Directory.systemTemp.createTempSync('dartbrew-create-');
      addTearDown(() => parent.deleteSync(recursive: true));
      final target = p.join(parent.path, name);
      final runner = CommandRunner<int>('dartbrew', 'test')
        ..addCommand(createCommand(sdkDir: () => sdk.root.path));
      await expectLater(
        runner.run(['create', target]),
        throwsA(
          isA<UsageException>().having(
            (e) => e.message,
            'message',
            contains('not a valid package name'),
          ),
        ),
      );
      expect(Directory(target).existsSync(), isFalse);
      expect(sdk.calls('dart'), isEmpty);
    });
  }

  test('a non-empty directory fails untouched unless --force', () async {
    final kept = <String>[];
    await expectLater(
      create(
        ['--no-pub'],
        prepare: (d) {
          File(p.join(d.path, 'keep.txt')).writeAsStringSync('x');
          kept.add(d.path);
        },
      ),
      throwsA(isA<FileSystemException>()),
    );
    expect(Directory(kept.single).listSync().map((e) => p.basename(e.path)), [
      'keep.txt',
    ]);
    final r = await create(
      ['--no-pub', '--force'],
      prepare: (d) {
        File(p.join(d.path, 'keep.txt')).writeAsStringSync('x');
        File(p.join(d.path, 'pubspec.yaml')).writeAsStringSync('old');
      },
    );
    expect(r.code, 0);
    expect(r.file('keep.txt').existsSync(), isTrue);
    expect(r.file('pubspec.yaml').readAsStringSync(), contains('name: snake'));
  });

  test('an empty existing directory is accepted', () async {
    final r = await create(['--no-pub'], prepare: (_) {});
    expect(r.code, 0);
  });

  test('--no-pub does not start dart', () async {
    final r = await create(['--no-pub']);
    expect(r.sdk.calls('dart'), isEmpty);
  });

  test('pub get runs once in the new directory', () async {
    final r = await create([]);
    expect(r.code, 0);
    expect(r.sdk.calls('dart'), [
      ['pub', 'get'],
    ]);
    expect(r.workingDirectories, [r.root.path]);
  });

  test(
    'the generated test imports only package:test and the library',
    () async {
      final r = await create(['--no-pub']);
      final imports = RegExp(
        r"^import '([^']+)';",
        multiLine: true,
      ).allMatches(r.file('test/snake_test.dart').readAsStringSync());
      expect(
        [for (final m in imports) m[1]],
        ['package:test/test.dart', 'package:snake/snake.dart'],
      );
    },
  );

  test(
    'a generated project analyzes and tests with the host SDK',
    () async {
      final r = await create(['--no-pub']);
      Future<void> dart(List<String> args) async {
        final result = await Process.run(
          Platform.resolvedExecutable,
          args,
          workingDirectory: r.root.path,
        );
        expect(result.exitCode, 0, reason: '${result.stdout}${result.stderr}');
      }

      await dart(['pub', 'get']);
      await dart(['analyze']);
      await dart(['test']);
      await dart(['run', 'bin/main.dart']);
    },
    skip: Platform.environment['DARTBREW_CREATE_INTEGRATION'] == '1'
        ? false
        : 'set DARTBREW_CREATE_INTEGRATION=1 to run',
    timeout: const Timeout(Duration(minutes: 5)),
  );
}
