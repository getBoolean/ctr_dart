import 'dart:io';

import 'package:args/command_runner.dart';
import 'package:dartbrew/src/commands/passthrough.dart';
import 'package:dartbrew/src/process.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

import 'support/fake_sdk.dart';

CommandRunner<int> runnerFor(FakeSdk sdk, [ProcessStarter? start]) {
  final runner = CommandRunner<int>('dartbrew', 'test');
  for (final command
      in start == null
          ? passthroughCommands(sdkDir: () => sdk.root.path)
          : passthroughCommands(sdkDir: () => sdk.root.path, start: start)) {
    runner.addCommand(command);
  }
  return runner;
}

class Run {
  final int? code;
  final FakeSdk sdk;
  final List<ProcessStartMode> modes;
  Run(this.code, this.sdk, this.modes);
}

Future<Run> run(
  List<String> args, {
  int exitCode = 0,
  bool modify = false,
}) async {
  final sdk = fakeSdk(tools: {'dart': exitCode});
  if (modify) {
    File(
      p.join(sdk.root.path, 'tools', 'dart.dart'),
    ).writeAsStringSync('// tampered\n', mode: FileMode.append);
  }
  final modes = <ProcessStartMode>[];
  final runner = runnerFor(sdk, (
    exe,
    args, {
    workingDirectory,
    environment,
    mode = ProcessStartMode.normal,
  }) {
    modes.add(mode);
    return startStub(exe, args);
  });
  final code = await runner.run(forwardHelpArguments(args));
  return Run(code, sdk, modes);
}

void main() {
  test('format forwards exact arguments and returns exit code 1', () async {
    final r = await run([
      'format',
      '--set-exit-if-changed',
      'lib',
    ], exitCode: 1);
    expect(r.code, 1);
    expect(r.sdk.calls('dart'), [
      ['format', '--set-exit-if-changed', 'lib'],
    ]);
    expect(r.modes, [ProcessStartMode.inheritStdio]);
  });

  test('pub get --offline passes through and returns 0', () async {
    final r = await run(['pub', 'get', '--offline']);
    expect(r.code, 0);
    expect(r.sdk.calls('dart'), [
      ['pub', 'get', '--offline'],
    ]);
  });

  test('analyze exit code 3 is returned unchanged', () async {
    final r = await run(['analyze'], exitCode: 3);
    expect(r.code, 3);
  });

  test('--help and help <command> are forwarded to the host dart', () async {
    for (final args in [
      ['format', '--help'],
      ['help', 'format'],
    ]) {
      final r = await run(args);
      expect(r.sdk.calls('dart'), [
        ['format', '--help'],
      ]);
    }
  });

  test('flags, -- and short options are not interpreted', () async {
    final r = await run(['fix', '--apply', '-x', '--', 'a']);
    expect(r.sdk.calls('dart'), [
      ['fix', '--apply', '-x', '--', 'a'],
    ]);
  });

  for (final name in unsupportedNames) {
    test('$name exits 64 as a usage error without starting dart', () async {
      final sdk = fakeSdk(tools: {'dart': 0});
      final runner = runnerFor(sdk);
      await expectLater(
        runner.run([name, '--anything']),
        throwsA(
          isA<UsageException>().having(
            (e) => e.message,
            'message',
            allOf(
              contains('not supported for the CTR target'),
              isNot(contains('3DS')),
            ),
          ),
        ),
      );
      expect(sdk.calls('dart'), isEmpty);
    });
  }

  test('a .dart file suggests dartbrew run', () {
    final message = unsupportedInvocationMessage(['hello.dart']);
    expect(message, contains('dartbrew run hello.dart'));
    expect(unsupportedInvocationMessage(['format', 'hello.dart']), isNull);
    expect(unsupportedInvocationMessage(['--version']), isNull);
    expect(unsupportedInvocationMessage([]), isNull);
  });

  test('quick verification lets a modified host-dart file pass', () async {
    final r = await run(['info'], modify: true);
    expect(r.code, 0);
    expect(r.sdk.calls('dart'), [
      ['info'],
    ]);
  });
}
