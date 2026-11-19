import 'dart:async';
import 'dart:io';

import 'package:path/path.dart' as p;

import '../process.dart';
import '../targets/ctr/package.dart';
import 'device.dart';

/// The launcher's cfg file and journal names on the SD card.
const _configName = 'ctr-runtime-run.cfg';
const _journalName = 'ctr-runtime.log';

/// The schema-2 `ctr-runtime-run.cfg` text for [identity] that tells the
/// launcher to connect to `127.0.0.1:<hostPort>`.
String azaharRunConfig(Map<String, Object> identity, int hostPort) =>
    '${runConfig(identity)}host=127.0.0.1:$hostPort\n';

/// Azahar at [executable], with its emulated SD card at [sdmc].
///
/// [launch] writes the run's cfg to the card and starts Azahar on the app;
/// the launcher reads the cfg and connects back over Azahar's host sockets.
/// Its journal on the card is the fallback when it does not. Azahar returns
/// to its game list when a program ends, so [dispose] closes it.
final class AzaharDevice implements JournalingDevice {
  final String executable;
  final String sdmc;
  final ProcessStarter start;

  /// The directory Azahar is started in, where Linux and macOS look for a
  /// portable `user/` directory.
  final String? workingDirectory;

  /// How often [journal] checks the journal for new bytes.
  final Duration pollInterval;

  Process? _process;
  int _journalStart = 0;

  AzaharDevice({
    required this.executable,
    required this.sdmc,
    this.start = startProcess,
    this.workingDirectory,
    this.pollInterval = const Duration(milliseconds: 200),
  });

  @override
  String get environment => 'azahar';

  File get _journalFile => File(p.join(sdmc, _journalName));

  @override
  Future<void> launch(
    File app,
    Map<String, Object> identity,
    int hostPort,
  ) async {
    File(p.join(sdmc, _configName))
      ..parent.createSync(recursive: true)
      ..writeAsStringSync(azaharRunConfig(identity, hostPort));
    final journal = _journalFile;
    _journalStart = journal.existsSync() ? journal.lengthSync() : 0;
    final process = await start(executable, [
      app.absolute.path,
    ], workingDirectory: workingDirectory);
    _process = process;
    process.stdout.drain<void>().ignore();
    process.stderr.drain<void>().ignore();
  }

  @override
  Stream<List<int>> journal() {
    final process = _process;
    if (process == null) throw StateError('Azahar has not been launched.');
    var offset = _journalStart;
    Timer? poll;
    late final StreamController<List<int>> controller;

    void read() {
      if (controller.isClosed) return;
      try {
        final file = _journalFile;
        if (!file.existsSync()) return;
        final length = file.lengthSync();
        if (length < offset) offset = 0; // Replaced since launch.
        if (length == offset) return;
        final handle = file.openSync();
        try {
          handle.setPositionSync(offset);
          final bytes = handle.readSync(length - offset);
          offset += bytes.length;
          if (bytes.isNotEmpty) controller.add(bytes);
        } finally {
          handle.closeSync();
        }
      } on FileSystemException {
        // Mid-write or briefly locked; the next poll retries.
      }
    }

    controller = StreamController<List<int>>(
      onListen: () {
        read();
        poll = Timer.periodic(pollInterval, (_) => read());
        process.exitCode.then((_) {
          if (controller.isClosed) return;
          poll?.cancel();
          read();
          controller.close();
        });
      },
      onCancel: () {
        poll?.cancel();
        if (!controller.isClosed) controller.close();
      },
    );
    return controller.stream;
  }

  /// Closes Azahar if it is running.
  @override
  Future<void> dispose() async {
    final process = _process;
    if (process == null) return;
    _process = null;
    process.kill();
    try {
      await process.exitCode.timeout(const Duration(seconds: 5));
    } on TimeoutException {
      process.kill(ProcessSignal.sigkill);
      await process.exitCode.timeout(
        const Duration(seconds: 5),
        onTimeout: () => -1,
      );
    }
  }
}
