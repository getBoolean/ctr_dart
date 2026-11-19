import 'package:args/args.dart';

import 'ctr/ctr_target.dart';

/// A build target: a device family that dartbrew compiles for, runs on and
/// tests on. Targets are chosen with `--target` and never get their own
/// commands, so adding one adds an allowed value only.
abstract interface class Target {
  /// The codename used as the `--target` value.
  String get name;

  /// One line shown next to the value in help text.
  String get description;
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
