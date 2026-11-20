import 'dart:async';
import 'dart:io';

import 'package:args/command_runner.dart';
import 'package:dartbrew/src/commands/compile.dart';
import 'package:dartbrew/src/commands/create.dart';
import 'package:dartbrew/src/commands/devices.dart';
import 'package:dartbrew/src/commands/run.dart';
import 'package:dartbrew/src/commands/test.dart';
import 'package:dartbrew/src/device/device.dart';
import 'package:dartbrew/src/device/transport.dart';
import 'package:dartbrew/src/process.dart';
import 'package:dartbrew/src/sdk.dart';
import 'package:dartbrew/src/targets/ctr/azahar.dart';
import 'package:dartbrew/src/targets/ctr/pipeline.dart';
import 'package:dartbrew/src/targets/target.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

import 'support/fake_sdk.dart';

/// Thrown by [_FakeTarget] to show a command reached it.
final class _Reached implements Exception {
  final String what;
  const _Reached(this.what);

  @override
  String toString() => 'reached $what';
}

final class _FakeTransport implements DeviceTransport {
  @override
  Stream<InternetAddress> discover(Duration wait) =>
      Stream.value(InternetAddress('10.0.0.9'));

  @override
  Future<void> upload(
    InternetAddress device,
    File app, {
    List<String> arguments = const [],
    void Function(int sent, int total)? onProgress,
  }) => throw const _Reached('upload');
}

/// A second target whose every operation is observable, to show commands
/// dispatch through the selected target rather than calling CTR code.
final class _FakeTarget implements Target {
  @override
  String get name => 'fake';

  @override
  String get description => 'A fake target.';

  @override
  String get applicationExtension => 'fake';

  @override
  Map<String, String> template(String packageName) => {'fake.txt': packageName};

  @override
  Future<CtrBuild> build({
    required NativeSdk sdk,
    required String project,
    required String entry,
    required BuildMode mode,
    required String fixture,
    required Directory work,
    required File application,
    bool offline = false,
    ProcessStarter start = startProcess,
    StringSink? warnings,
  }) => throw _Reached('build ${p.basename(application.path)}');

  @override
  Map<String, Object> package(
    NativeSdk sdk,
    CtrBuild build,
    Directory output,
  ) => throw const _Reached('package');

  @override
  List<String> kernelArguments(
    NativeSdk sdk, {
    required BuildMode mode,
    required File packageConfig,
    required String output,
    required String entry,
  }) => throw const _Reached('kernel arguments');

  @override
  DeviceTransport transport() => _FakeTransport();

  @override
  String? findEmulator(AzaharHost host) => '/fake/emulator';

  @override
  ({RunDevice device, String description}) emulator({
    required AzaharHost host,
    String? path,
    ProcessStarter start = startProcess,
  }) => throw const AzaharNotFound('The fake emulator is not installed.');

  @override
  File writeTestEntrypoint({
    required String project,
    required List<String> testFiles,
    List<String> names = const [],
    List<String> plainNames = const [],
    int firstId = 0,
  }) => throw const _Reached('test entrypoint');

  @override
  String? testEntrypointWarning(String project) => null;
}

void main() {
  late Directory dir;
  setUp(() {
    targets['fake'] = _FakeTarget();
    dir = Directory.systemTemp.createTempSync('target_test');
  });
  tearDown(() {
    targets.remove('fake');
    dir.deleteSync(recursive: true);
  });

  /// A project with `bin/main.dart` and `test/a_test.dart`.
  String project() {
    final root = p.join(dir.path, 'app');
    File(p.join(root, 'pubspec.yaml'))
      ..createSync(recursive: true)
      ..writeAsStringSync('name: app\n');
    File(p.join(root, 'bin', 'main.dart'))
      ..createSync(recursive: true)
      ..writeAsStringSync('void main() {}\n');
    File(p.join(root, 'test', 'a_test.dart'))
      ..createSync(recursive: true)
      ..writeAsStringSync('void main() {}\n');
    return Directory(root).resolveSymbolicLinksSync();
  }

  test('devices lists the selected target\'s consoles and emulator', () async {
    final out = StringBuffer();
    final runner = CommandRunner<int>('dartbrew', '')
      ..addCommand(devicesCommand(out: out, err: StringBuffer()));
    final code = await runner.run([
      'devices',
      '--target',
      'fake',
      '--wait',
      '0',
    ]);
    expect(code, 0);
    expect(out.toString(), contains('console  10.0.0.9'));
    expect(out.toString(), contains('azahar   /fake/emulator'));
  });

  test('create writes the selected target\'s template', () async {
    final target = p.join(dir.path, 'made');
    final runner = CommandRunner<int>('dartbrew', '')
      ..addCommand(createCommand());
    await runner.run(['create', '--target', 'fake', '--no-pub', target]);
    expect(File(p.join(target, 'fake.txt')).readAsStringSync(), 'made');
    expect(File(p.join(target, 'pubspec.yaml')).existsSync(), isFalse);
  });

  test('compile builds with the selected target', () async {
    final sdk = fakeSdk();
    final root = project();
    final runner = CommandRunner<int>('dartbrew', '')
      ..addCommand(compileCommand());
    await expectLater(
      runner.run([
        'compile',
        '--target',
        'fake',
        '--sdk',
        sdk.root.path,
        '-o',
        p.join(dir.path, 'out'),
        p.join(root, 'bin', 'main.dart'),
      ]),
      throwsA(
        isA<_Reached>().having((e) => e.what, 'what', 'build application.fake'),
      ),
    );
  });

  test('run -d azahar uses the selected target\'s emulator', () async {
    final err = StringBuffer();
    final runner = CommandRunner<int>('dartbrew', '')
      ..addCommand(runCommand(out: StringBuffer(), err: err));
    final code = await runner.run([
      'run',
      '--target',
      'fake',
      '-d',
      'azahar',
      '--project-directory',
      project(),
    ]);
    expect(code, 1);
    expect(err.toString(), contains('The fake emulator is not installed.'));
  });

  test('test writes the selected target\'s test entrypoint', () async {
    final runner = CommandRunner<int>('dartbrew', '')
      ..addCommand(testCommand(out: StringBuffer(), err: StringBuffer()));
    await expectLater(
      runner.run([
        'test',
        '--target',
        'fake',
        '--project-directory',
        project(),
      ]),
      throwsA(isA<_Reached>().having((e) => e.what, 'what', 'test entrypoint')),
    );
  });
}
