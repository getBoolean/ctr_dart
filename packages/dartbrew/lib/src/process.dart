import 'dart:io';

/// Starts a child process. Commands take one of these so tests can run them
/// against stub executables.
typedef ProcessStarter =
    Future<Process> Function(
      String executable,
      List<String> arguments, {
      String? workingDirectory,
      Map<String, String>? environment,
      ProcessStartMode mode,
    });

/// The real [ProcessStarter]: [Process.start] without a shell.
Future<Process> startProcess(
  String executable,
  List<String> arguments, {
  String? workingDirectory,
  Map<String, String>? environment,
  ProcessStartMode mode = ProcessStartMode.normal,
}) => Process.start(
  executable,
  arguments,
  workingDirectory: workingDirectory,
  environment: environment,
  runInShell: false,
  mode: mode,
);
