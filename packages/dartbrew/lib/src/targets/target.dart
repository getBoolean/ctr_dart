import 'dart:io';

import 'package:args/args.dart';

import '../device/device.dart';
import '../device/transport.dart';
import '../process.dart';
import '../sdk.dart';
import 'ctr/azahar.dart';
import 'ctr/ctr_target.dart';
import 'ctr/pipeline.dart';

/// A build target: a device family that dartbrew compiles for, runs on and
/// tests on. Targets are chosen with `--target` and never get their own
/// commands, so adding one adds an allowed value only.
///
/// A target owns its compile pipeline, packaging, project template, device
/// transports and test entrypoint; commands reach them only through the
/// selected target.
abstract interface class Target {
  /// The codename used as the `--target` value.
  String get name;

  /// One line shown next to the value in help text.
  String get description;

  /// The file extension of a built application, without the dot.
  String get applicationExtension;

  /// The files of a new project named [packageName], keyed by relative path
  /// with `/` separators.
  Map<String, String> template(String packageName);

  /// Compiles [entry] in [project] into the binary [application], with
  /// intermediate files in [work]. A failed stage throws a `StageFailure`
  /// and [application] is not written. Metadata warnings go to [warnings].
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
  });

  /// Packages [build] into [output] for a manual run from the device's
  /// storage and returns the new run identity.
  Map<String, Object> package(NativeSdk sdk, CtrBuild build, Directory output);

  /// The kernel compiler arguments that compile [entry] to [output] for
  /// [mode], resolving packages with [packageConfig] when it exists.
  List<String> kernelArguments(
    NativeSdk sdk, {
    required BuildMode mode,
    required File packageConfig,
    required String output,
    required String entry,
  });

  /// The network transport that finds this target's devices and sends apps
  /// to them.
  DeviceTransport transport();

  /// Where this target's emulator is installed on [host], or null when it
  /// is not found.
  String? findEmulator(AzaharHost host);

  /// The emulator device to run on, found on [host] or at [path], with a
  /// description of it for messages. Throws an [AzaharNotFound] when the
  /// emulator or its storage cannot be found.
  ({RunDevice device, String description}) emulator({
    required AzaharHost host,
    String? path,
    ProcessStarter start = startProcess,
  });

  /// Writes the program that runs [testFiles] (absolute paths inside
  /// [project]) on the device and reports their results as test events,
  /// and returns it. A test runs only when its full name matches every
  /// pattern in [names] and contains every string in [plainNames]. Event IDs
  /// start at [firstId].
  File writeTestEntrypoint({
    required String project,
    required List<String> testFiles,
    List<String> names = const [],
    List<String> plainNames = const [],
    int firstId = 0,
  });

  /// A warning that [project]'s test packages may not work with the test
  /// entrypoint, or null when they should.
  String? testEntrypointWarning(String project);
}

/// Every known target, keyed by [Target.name].
final Map<String, Target> targets = {
  for (final target in const <Target>[CtrTarget()]) target.name: target,
};

/// The target used when `--target` is not given.
const defaultTarget = 'ctr';

/// Adds the shared `--target` option to [parser].
void addTargetOption(ArgParser parser) {
  parser.addOption(
    'target',
    help: 'The build target.',
    allowed: targets.keys,
    allowedHelp: {
      for (final target in targets.values) target.name: target.description,
    },
    defaultsTo: defaultTarget,
  );
}

/// The target selected by an option added with [addTargetOption].
Target selectedTarget(ArgResults results) => targets[results.option('target')]!;
