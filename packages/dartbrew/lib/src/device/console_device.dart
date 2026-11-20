import 'dart:async';
import 'dart:io';

import '../targets/ctr/netloader.dart';
import 'device.dart';
import 'transport.dart';

/// The run identity keys passed to the launcher in argv, in this order.
const _argvIdentityKeys = [
  'schema',
  'run_id',
  'artifact_sha256',
  'environment',
  'fixture',
  'mode',
  'compatibility',
  'build_id',
];

/// The launcher's schema-2 argv tokens for [identity] and the host listener
/// on [hostPort] (see the "Launcher contract (schema 2)" runbook section).
///
/// The optional linked-value tokens are included too; they always equal the
/// values linked into the uploaded app.
List<String> launcherArguments(Map<String, Object> identity, int hostPort) => [
  for (final key in _argvIdentityKeys) '--ctr-run=$key=${identity[key]}',
  '--ctr-host-port=$hostPort',
];

/// A console reached through its netloader at [address].
final class ConsoleDevice implements RunDevice {
  final DeviceTransport transport;
  final InternetAddress address;

  /// Where upload progress is reported; standard error by default.
  final StringSink progress;

  ConsoleDevice(this.transport, this.address, {StringSink? progress})
    : progress = progress ?? stderr;

  @override
  String get environment => 'hardware';

  @override
  bool acceptsPeer(InternetAddress address) =>
      address.type == this.address.type &&
      address.address == this.address.address;

  /// Uploads [app] under its own file name, so the console saves it as
  /// `sdmc:/3ds/<name>` and repeated runs overwrite it.
  @override
  Future<void> launch(File app, Map<String, Object> identity, int hostPort) =>
      transport.upload(
        address,
        app,
        arguments: launcherArguments(identity, hostPort),
        onProgress: _reportProgress(),
      );

  /// Reports each further tenth of the upload, since a large app can take
  /// minutes on console Wi-Fi.
  void Function(int, int) _reportProgress() {
    var reported = 0;
    return (sent, total) {
      final tenths = total == 0 ? 10 : sent * 10 ~/ total;
      if (tenths <= reported) return;
      reported = tenths;
      String mb(int bytes) => (bytes / (1024 * 1024)).toStringAsFixed(1);
      progress.writeln(
        'Uploaded ${tenths * 10}% (${mb(sent)} of ${mb(total)} MB).',
      );
    };
  }

  @override
  Future<void> dispose() async {}
}

/// Why no single console could be chosen.
final class ConsoleSelectionException implements Exception {
  /// The exit code: 1 when none answered, 64 when several did.
  final int exitCode;
  final String message;

  const ConsoleSelectionException(this.exitCode, this.message);

  @override
  String toString() => message;
}

/// Finds the one console whose netloader answers within [wait].
///
/// Tells [prompt] to open the netloader first. Once a console answers,
/// listens [settle] longer so a second console is noticed rather than picked
/// at random. Throws a [ConsoleSelectionException] when none or several
/// answer, and passes on the transport's [NetloaderException]s.
Future<InternetAddress> discoverConsole(
  DeviceTransport transport, {
  required Duration wait,
  Duration settle = const Duration(seconds: 1),
  required StringSink prompt,
}) async {
  prompt.writeln(
    'Waiting up to ${_seconds(wait)} for a console. Open the netloader in '
    'Homebrew Launcher on the console (press Y).',
  );
  final found = <InternetAddress>[];
  final done = Completer<void>();
  Timer? settling;
  late final StreamSubscription<InternetAddress> subscription;
  subscription = transport
      .discover(wait)
      .listen(
        (address) {
          found.add(address);
          settling ??= Timer(settle, () {
            if (!done.isCompleted) done.complete();
          });
        },
        onError: (Object error, StackTrace stack) {
          if (!done.isCompleted) done.completeError(error, stack);
        },
        onDone: () {
          if (!done.isCompleted) done.complete();
        },
        cancelOnError: true,
      );
  try {
    await done.future;
  } finally {
    settling?.cancel();
    await subscription.cancel();
  }
  if (found.isEmpty) {
    throw ConsoleSelectionException(
      1,
      'No console answered within ${_seconds(wait)}. Open Homebrew Launcher '
      'on the console and press Y to start the netloader, then run again. '
      'If the netloader is waiting and still not found, allow UDP port '
      '$netloaderPort through this computer\'s firewall, or pass the '
      'console\'s address with -d <ip>.',
    );
  }
  if (found.length > 1) {
    throw ConsoleSelectionException(
      64,
      'Found ${found.length} consoles; choose one with -d <ip>:\n'
      '${found.map((a) => '  ${a.address}').join('\n')}',
    );
  }
  return found.single;
}

String _seconds(Duration duration) {
  final seconds = duration.inMilliseconds / 1000;
  return '${seconds == seconds.roundToDouble() ? seconds.round() : seconds} s';
}
