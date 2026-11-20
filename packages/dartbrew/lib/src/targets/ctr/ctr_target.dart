import 'dart:io';

import '../../device/azahar_device.dart';
import '../../device/device.dart';
import '../../device/transport.dart';
import '../../process.dart';
import '../../sdk.dart';
import '../target.dart';
import 'azahar.dart';
import 'netloader.dart';
import 'package.dart';
import 'pipeline.dart' as pipeline;
import 'pipeline.dart' show BuildMode, CtrBuild;
import 'templates.dart';
import 'test_entrypoint.dart' as entrypoint;

/// The CTR target: homebrew apps launched from Homebrew Launcher.
final class CtrTarget implements Target {
  const CtrTarget();

  @override
  String get name => 'ctr';

  @override
  String get description => 'CTR homebrew applications (.3dsx).';

  @override
  String get applicationExtension => '3dsx';

  @override
  Map<String, String> template(String packageName) => ctrTemplate(packageName);

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
  }) => pipeline.buildCtrApplication(
    sdk: sdk,
    project: project,
    entry: entry,
    mode: mode,
    fixture: fixture,
    work: work,
    application: application,
    offline: offline,
    start: start,
    warnings: warnings,
  );

  @override
  Map<String, Object> package(
    NativeSdk sdk,
    CtrBuild build,
    Directory output,
  ) => packageCtrApplication(sdk, build, output);

  @override
  List<String> kernelArguments(
    NativeSdk sdk, {
    required BuildMode mode,
    required File packageConfig,
    required String output,
    required String entry,
  }) => pipeline.kernelArguments(
    sdk,
    mode: mode,
    packageConfig: packageConfig,
    output: output,
    entry: entry,
  );

  @override
  DeviceTransport transport() => NetloaderClient();

  @override
  String? findEmulator(AzaharHost host) => findAzahar(host);

  @override
  ({RunDevice device, String description}) emulator({
    required AzaharHost host,
    String? path,
    ProcessStarter start = startProcess,
  }) {
    final executable = locateAzahar(host, path: path);
    return (
      device: AzaharDevice(
        executable: executable,
        sdmc: azaharSdmc(executable, host),
        start: start,
        workingDirectory: host.currentDirectory,
      ),
      description: 'Azahar ($executable)',
    );
  }

  @override
  File writeTestEntrypoint({
    required String project,
    required List<String> testFiles,
    List<String> names = const [],
    List<String> plainNames = const [],
    int firstId = 0,
  }) => entrypoint.writeTestEntrypoint(
    project: project,
    testFiles: testFiles,
    names: names,
    plainNames: plainNames,
    firstId: firstId,
  );

  @override
  String? testEntrypointWarning(String project) {
    final testApi = entrypoint.resolvedTestApiVersion(project);
    if (testApi == null || entrypoint.isTestedTestApi(testApi)) return null;
    return 'Warning: this project resolves test_api $testApi, but dartbrew '
        'test is tested with test_api ${entrypoint.testedTestApi}. If the '
        'test build fails or results look wrong, use a test package version '
        'that resolves test_api ${entrypoint.testedTestApi}.';
  }
}
