import 'dart:async';
import 'dart:io';

import 'stream.dart';
import 'verdict.dart';

/// A device that `run` and `test` start an app on: a console or an emulator.
abstract interface class RunDevice {
  /// The `environment` identity value of runs on this device.
  String get environment;

  /// Sends [app] to the device and starts it with the run [identity], telling
  /// it to connect back to the host listener on [hostPort].
  ///
  /// Completes once the device has accepted the app; the connect deadline
  /// starts then.
  Future<void> launch(File app, Map<String, Object> identity, int hostPort);

  /// Releases the device after the run, for example by closing an emulator.
  Future<void> dispose();
}

/// How long a run may stay silent before the host gives up.
final class RunDeadlines {
  /// How long after [RunDevice.launch] the app has to connect back.
  final Duration connect;

  /// How long the connection may carry no bytes, keepalives included,
  /// before it counts as lost.
  final Duration idle;

  /// The longest the whole run may take after launch, or null for no limit.
  final Duration? timeout;

  const RunDeadlines({
    this.connect = const Duration(seconds: 15),
    this.idle = const Duration(seconds: 10),
    this.timeout,
  });
}

/// The result of [runOnDevice].
final class RunResult {
  final Verdict verdict;
  final StreamEnd end;

  /// The exit code and message for [verdict] and [end] (see [exitFor]).
  final RunExit exit;

  const RunResult(this.verdict, this.end, this.exit);
}

/// Launches [app] on [device] and streams its records from the first
/// connection to [listener] until the app closes the connection or a
/// deadline passes.
///
/// [listener] must already be bound, so a fast app cannot miss it. Each
/// accepted output record's text goes to [onOutput] as it arrives. Later
/// connections are refused. The listener is left open for the caller to
/// close, and [device] is not disposed.
///
/// Throws whatever [RunDevice.launch] throws, such as a
/// `NetloaderException`.
Future<RunResult> runOnDevice({
  required RunDevice device,
  required File app,
  required Map<String, Object> identity,
  required ServerSocket listener,
  RunDeadlines deadlines = const RunDeadlines(),
  void Function(String text)? onOutput,
}) async {
  final accumulator = VerdictAccumulator(identity);
  final parser = RuntimeLineParser();
  final ended = Completer<StreamEnd>();
  void end(StreamEnd reason) {
    if (!ended.isCompleted) ended.complete(reason);
  }

  void feed(List<RuntimeLine> lines) {
    for (final line in lines) {
      final text = accumulator.add(line);
      if (text != null) onOutput?.call(text);
    }
  }

  Socket? connection;
  Timer? idle;
  final accepting = listener.listen((socket) {
    if (connection != null || ended.isCompleted) {
      socket.destroy();
      return;
    }
    connection = socket;
    idle = Timer(deadlines.idle, () => end(StreamEnd.idleTimeout));
    socket.listen(
      (chunk) {
        if (ended.isCompleted) return;
        idle?.cancel();
        idle = Timer(deadlines.idle, () => end(StreamEnd.idleTimeout));
        feed(parser.feed(chunk));
      },
      onDone: () => end(StreamEnd.closed),
      onError: (Object _) => end(StreamEnd.closed),
      cancelOnError: true,
    );
  }, onError: (Object _) {});

  Timer? connect;
  Timer? overall;
  try {
    await device.launch(app, identity, listener.port);
    if (connection == null) {
      connect = Timer(deadlines.connect, () {
        if (connection == null) end(StreamEnd.connectTimeout);
      });
    }
    if (deadlines.timeout case final timeout?) {
      overall = Timer(timeout, () => end(StreamEnd.userTimeout));
    }
    final reason = await ended.future;
    if (reason == StreamEnd.closed) feed(parser.close());
    final verdict = accumulator.finish();
    return RunResult(
      verdict,
      reason,
      exitFor(verdict, reason, port: listener.port),
    );
  } finally {
    connect?.cancel();
    overall?.cancel();
    idle?.cancel();
    await accepting.cancel();
    connection?.destroy();
  }
}
