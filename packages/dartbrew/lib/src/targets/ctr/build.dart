import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:args/command_runner.dart';
import 'package:crypto/crypto.dart';
import 'package:path/path.dart' as p;

import '../../commands/doctor.dart';
import '../../native_directory.dart';
import '../../native_elf.dart';
import '../../process.dart';
import '../../sdk.dart';
import '../../stage_runner.dart';

String programAssembly(
  String mode,
  String fixture,
  String compatibility,
  String buildId,
  int kernelSize,
) {
  final payload = mode == 'aot'
      ? '_kDartSnapshotData, _kDartSnapshotText, 0, 0'
      : '0, 0, ctr_kernel, $kernelSize';
  final values = {
    'ctr_fixture': fixture,
    'ctr_mode': mode,
    'ctr_compatibility': compatibility,
    'ctr_build_id': buildId,
  };
  return '''.section .rodata.ctr_program,"a",%progbits
.balign 4
.global ctr_program
.type ctr_program,%object
ctr_program:
.word $payload
.word ctr_fixture, ctr_mode, ctr_compatibility, ctr_build_id
.size ctr_program, 32
${values.entries.map((e) => '${e.key}:\n.asciz ${jsonEncode(e.value)}').join('\n')}
.section .note.GNU-stack,"",%progbits
''';
}

/// Compiles and stages a Dart application for the CTR target.
///
/// Not registered in the runner; kept as the implementation that the
/// `compile` command takes over.
class BuildCommand extends Command<int> {
  @override
  String get name => 'build';
  @override
  String get description => 'Compile and stage a Dart application.';
  final ProcessStarter _start;

  BuildCommand({ProcessStarter start = startProcess}) : _start = start {
    addSdkOption(argParser);
    argParser
      ..addOption('mode', allowed: ['aot', 'jit'], defaultsTo: 'aot')
      ..addOption('output', abbr: 'o')
      ..addOption('project-directory')
      ..addFlag(
        'offline',
        help: 'Resolve packages using only the local pub cache.',
      )
      ..addOption('fixture', defaultsTo: 'app');
  }

  @override
  Future<int> run() async {
    final args = argResults!;
    if (args.rest.length != 1 || args.option('output') == null) {
      throw UsageException(
        'Build requires one entrypoint and --output.',
        usage,
      );
    }
    final sdk = await NativeSdk.load(sdkDirectory(args));
    final entry = File(args.rest.single).resolveSymbolicLinksSync();
    final project = Directory(
      args.option('project-directory') ?? p.dirname(entry),
    ).resolveSymbolicLinksSync();
    if (!p.isWithin(project, entry)) {
      throw const FormatException(
        'Entrypoint must be inside the selected project.',
      );
    }
    final output = Directory(p.normalize(p.absolute(args.option('output')!)));
    if (FileSystemEntity.typeSync(output.path) !=
        FileSystemEntityType.notFound) {
      throw const FormatException(
        'Output already exists; choose a new directory.',
      );
    }
    if (p.equals(sdk.root, output.path) || p.isWithin(sdk.root, output.path)) {
      throw const FormatException('Build output must be outside the SDK.');
    }
    final fixture = args.option('fixture')!;
    if (!RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch(fixture)) {
      throw const FormatException(
        'Fixture must contain 1-64 letters, digits, underscores or hyphens.',
      );
    }
    await buildApplication(
      sdk,
      entry,
      project,
      output,
      args.option('mode')!,
      fixture,
      args.flag('offline'),
      start: _start,
    );
    stdout.writeln('Built ${p.join(output.path, 'application.3dsx')}');
    stdout.writeln(
      'Copy SDROOT contents to the SD card, then launch the app in Homebrew Launcher.',
    );
    return 0;
  }
}

/// Builds [entry] into [output]: application.3dsx, artifact.json, run.json,
/// the staged SD-card folder, and per-stage logs under `work/`.
Future<void> buildApplication(
  NativeSdk sdk,
  String entry,
  String project,
  Directory output,
  String mode,
  String fixture,
  bool offline, {
  ProcessStarter start = startProcess,
}) async {
  output.parent.createSync(recursive: true);
  createDirectoryExclusively(output.path);
  final work = Directory(p.join(output.path, 'work'))..createSync();
  final run = StageRunner(sdk, work, start: start);

  final packageConfig = File(p.join(project, '.dart_tool/package_config.json'));
  if (File(p.join(project, 'pubspec.yaml')).existsSync()) {
    await run(
      'dart',
      ['pub', 'get', if (offline) '--offline'],
      'packages',
      cwd: project,
    );
  }
  final kernel = p.join(work.path, 'application.dill');
  await run('kernel', [
    if (mode == 'aot') '--aot',
    '--platform=${sdk.asset(sdk.runtime['platform'] as String)}',
    if (packageConfig.existsSync()) '--packages=${packageConfig.path}',
    '--output=$kernel',
    entry,
  ], 'kernel');
  final assembly = File(p.join(work.path, 'payload.S'));
  if (mode == 'aot') {
    await run('snapshot', [
      '--snapshot_kind=app-aot-assembly',
      '--assembly=${assembly.path}',
      kernel,
    ], 'snapshot');
  } else {
    assembly.writeAsStringSync(
      '.section .rodata\n.balign 16\n.global ctr_kernel\nctr_kernel:\n'
      '.incbin "application.dill"\n.section .note.GNU-stack,"",%progbits\n',
    );
  }
  final runtime = sdk.runtime;
  final profile = (runtime['modes'] as Map)[mode] as Map;
  final compatibility = profile['compatibility'] as String;
  final payloadHash = await fileDigest(
    File(mode == 'aot' ? assembly.path : kernel),
  );
  final sdkHash = await fileDigest(File(p.join(sdk.root, 'sdk.json')));
  final buildId = sha256
      .convert(utf8.encode(jsonEncode([sdkHash, mode, fixture, payloadHash])))
      .toString();
  final program = File(p.join(work.path, 'program.S'))
    ..writeAsStringSync(
      programAssembly(
        mode,
        fixture,
        compatibility,
        buildId,
        File(kernel).lengthSync(),
      ),
    );
  for (final source in [assembly, program]) {
    await run('as', [
      '-march=armv6k',
      '-mfpu=vfp',
      '-mfloat-abi=hard',
      source.path,
      '-o',
      p.setExtension(source.path, '.o'),
    ], 'assemble-${p.basenameWithoutExtension(source.path)}');
  }
  final link = runtime['link'] as Map;
  List<String> assets(String key) =>
      (link[key] as List).cast<String>().map(sdk.asset).toList();
  final elf = File(p.join(work.path, 'application.elf'));
  await run('ld', [
    '--defsym=__sync_synchronize=__sync_synchronize_cp15dmb',
    '-X',
    '-T',
    sdk.asset(link['layout'] as String),
    '-d',
    '--emit-relocs',
    '--use-blx',
    '--gc-sections',
    '-u',
    '__sync_synchronize_cp15dmb',
    '-Map=${p.join(work.path, 'link.map')}',
    '-o',
    elf.path,
    ...assets('startup'),
    ...(profile['objects'] as List).cast<String>().map(sdk.asset),
    p.join(work.path, 'program.o'),
    p.join(work.path, 'payload.o'),
    sdk.asset(link['math'] as String),
    sdk.asset(profile['archive'] as String),
    ...assets('libraries'),
    '--start-group',
    ...assets('grouped'),
    '--end-group',
    ...assets('end'),
  ], 'link');
  final binary = File(p.join(output.path, 'application.3dsx'))
    ..writeAsBytesSync(encode3dsx(elf.readAsBytesSync()));
  final record = {
    'schema': 1,
    'scope': 'compile-link-package-only',
    'fixture': fixture,
    'mode': mode,
    'compatibility': compatibility,
    'build_id': buildId,
    'artifact_sha256': await fileDigest(binary),
    'payload_sha256': payloadHash,
    'elf_sha256': await fileDigest(elf),
    'sdk_head': runtime['sdk_head'],
    'sdk_manifest_sha256': sdkHash,
  };
  File(
    p.join(output.path, 'artifact.json'),
  ).writeAsStringSync('${jsonEncode(record)}\n');
  final random = Random.secure();
  final runId = List.generate(
    16,
    (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
  // The native launcher consumes these eight lines in this exact order.
  final identity = {
    'schema': 1,
    'run_id': runId,
    'fixture': fixture,
    'mode': mode,
    'compatibility': compatibility,
    'artifact_sha256': record['artifact_sha256'],
    'build_id': buildId,
    'environment': 'hardware',
  };
  final name = 'ctr-dart-$mode-${runId.substring(0, 8)}';
  final destination = File(
    p.join(output.path, 'SDROOT/3ds', name, '$name.3dsx'),
  );
  destination.parent.createSync(recursive: true);
  binary.copySync(destination.path);
  for (final relative in (sdk.manifest['files'] as Map).keys.cast<String>()) {
    if (!relative.startsWith('notices/')) continue;
    final notice = File(p.join(destination.parent.path, relative));
    notice.parent.createSync(recursive: true);
    File(sdk.asset(relative)).copySync(notice.path);
  }
  File(
    p.join(output.path, 'run.json'),
  ).writeAsStringSync('${jsonEncode(identity)}\n');
  File(p.join(output.path, 'SDROOT/ctr-runtime-run.cfg')).writeAsStringSync(
    identity.entries.map((e) => '${e.key}=${e.value}\n').join(),
  );
}
