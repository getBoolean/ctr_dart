import 'dart:io';

import 'package:args/args.dart';
import 'package:args/command_runner.dart';

import '../process.dart';
import '../sdk.dart';
import 'doctor.dart';

/// `dart` commands that run unchanged through the bundled host Dart.
const passthroughNames = ['pub', 'analyze', 'format', 'fix', 'doc', 'info'];

/// `dart` commands that dartbrew does not support for the CTR target.
const unsupportedNames = [
  'build',
  'install',
  'installed',
  'uninstall',
  'migrate',
  'devtools',
];

/// The passthrough and known-unsupported commands, ready for
/// `CommandRunner.addCommand`.
///
/// [start] launches the host Dart. [sdkDir] chooses the SDK directory and
/// defaults to the directory containing dartbrew.
List<Command<int>> passthroughCommands({
  ProcessStarter start = startProcess,
  String Function()? sdkDir,
}) => [
  for (final name in passthroughNames)
    _PassthroughCommand(name, start, sdkDir ?? _defaultSdkDirectory),
  for (final name in unsupportedNames) _UnsupportedCommand(name),
];

String _defaultSdkDirectory() => sdkDirectory(ArgParser().parse(const []));

/// Rewrites `help <passthrough command>` to `<command> --help`, so the host
/// `dart` prints its own help. Returns [arguments] otherwise.
List<String> forwardHelpArguments(List<String> arguments) {
  if (arguments.length == 2 &&
      arguments.first == 'help' &&
      passthroughNames.contains(arguments.last)) {
    return [arguments.last, '--help'];
  }
  return arguments;
}

/// A usage message for an invocation no command can handle, such as running
/// a `.dart` file directly, or null when [arguments] are not such a call.
String? unsupportedInvocationMessage(List<String> arguments) {
  if (arguments.isEmpty || arguments.first.startsWith('-')) return null;
  final file = arguments.first;
  if (!file.endsWith('.dart')) return null;
  return 'Running "$file" directly is not supported. '
      'Use "dartbrew run $file" instead.';
}

class _PassthroughCommand extends Command<int> {
  @override
  final String name;
  final ProcessStarter _start;
  final String Function() _sdkDir;

  _PassthroughCommand(this.name, this._start, this._sdkDir);

  @override
  final ArgParser argParser = ArgParser.allowAnything();

  @override
  String get description => 'Run "dart $name" with the bundled Dart SDK.';

  @override
  Future<int> run() async {
    final sdk = await NativeSdk.load(_sdkDir(), quick: true);
    final process = await _start(sdk.tool('dart'), [
      name,
      ...argResults!.arguments,
    ], mode: ProcessStartMode.inheritStdio);
    return process.exitCode;
  }
}

class _UnsupportedCommand extends Command<int> {
  @override
  final String name;

  _UnsupportedCommand(this.name);

  @override
  final ArgParser argParser = ArgParser.allowAnything();

  @override
  bool get hidden => true;

  @override
  String get description => '"dart $name" is not supported for the CTR target.';

  @override
  int run() => throw UsageException(
    '"$name" is not supported for the CTR target.',
    usage,
  );
}
