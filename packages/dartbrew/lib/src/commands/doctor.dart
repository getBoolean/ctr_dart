import 'dart:io';

import 'package:args/args.dart';
import 'package:args/command_runner.dart';
import 'package:path/path.dart' as p;

import '../sdk.dart';

/// Adds the shared `--sdk` option to [parser].
void addSdkOption(ArgParser parser) {
  parser.addOption(
    'sdk',
    help: 'SDK directory; defaults to the directory containing dartbrew.',
  );
}

/// The SDK directory chosen by an option added with [addSdkOption].
String sdkDirectory(ArgResults results) =>
    results.option('sdk') ?? p.dirname(Platform.resolvedExecutable);

class DoctorCommand extends Command<int> {
  @override
  String get name => 'doctor';

  @override
  String get description => 'Verify the bundled tools and runtime assets.';

  DoctorCommand() {
    addSdkOption(argParser);
  }

  @override
  Future<int> run() async {
    final args = argResults!;
    if (args.rest.isNotEmpty) {
      throw UsageException('doctor takes no arguments.', usage);
    }
    final sdk = await NativeSdk.load(sdkDirectory(args));
    stdout.writeln(
      'Verified native SDK for ${currentHost()}; '
      '${(sdk.manifest['files'] as Map<String, dynamic>).length} assets.',
    );
    return 0;
  }
}
