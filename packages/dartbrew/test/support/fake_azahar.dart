import 'dart:io';

import 'package:path/path.dart' as p;

/// How a fake Azahar's launcher reports.
enum FakeAzaharMode {
  /// Connects to the cfg's host line and sends a passing run.
  socket,

  /// Never connects; appends a failing run of an older run ID, then the
  /// current run with [FakeAzahar.journalOutcome], to the journal.
  journal,
}

/// A stub Azahar: a Dart script, started with the current VM by `startStub`,
/// that reads `ctr-runtime-run.cfg` from [sdmc] the way the launcher does,
/// reports as [mode] says, then stays open like Azahar at its game list.
///
/// It writes the app path it was given to `<sdmc>/fake-azahar-app.txt`.
final class FakeAzahar {
  final File script;
  final String sdmc;

  FakeAzahar._(this.script, this.sdmc);

  /// Writes the stub into [directory].
  factory FakeAzahar.create(
    Directory directory, {
    required String sdmc,
    required FakeAzaharMode mode,
    String journalOutcome = 'pass',
  }) {
    final script = File(p.join(directory.path, 'azahar.dart'))
      ..writeAsStringSync(_source(sdmc, mode, journalOutcome));
    return FakeAzahar._(script, sdmc);
  }

  String get appArgument =>
      File(p.join(sdmc, 'fake-azahar-app.txt')).readAsStringSync();
}

String _source(String sdmc, FakeAzaharMode mode, String outcome) =>
    '''
import 'dart:convert';
import 'dart:io';

const sdmc = r'$sdmc';

Future<void> main(List<String> args) async {
  File('\$sdmc/fake-azahar-app.txt').writeAsStringSync(args.join(' '));
  final cfg = {
    for (final line in File('\$sdmc/ctr-runtime-run.cfg').readAsLinesSync())
      line.substring(0, line.indexOf('=')): line.substring(line.indexOf('=') + 1),
  };
  String record(String runId, Map<String, Object?> fields) =>
      'CTR_RUNTIME \${jsonEncode({...fields, 'run_id': runId})}\\n';
  List<String> run(String runId, String outcome, String text) => [
    record(runId, {
      'event': 'begin',
      'schema': int.parse(cfg['schema']!),
      for (final key in [
        'fixture',
        'mode',
        'compatibility',
        'artifact_sha256',
        'build_id',
        'environment',
      ])
        key: cfg[key],
    }),
    record(runId, {'event': 'output', 'text': text}),
    record(runId, {'event': 'assert', 'name': 'cleanup', 'status': outcome}),
    record(runId, {'event': 'terminal', 'outcome': outcome, 'assertions': 1}),
  ];
  final runId = cfg['run_id']!;
  if ('${mode.name}' == 'socket') {
    final host = cfg['host']!.split(':');
    final socket = await Socket.connect(host[0], int.parse(host[1]));
    run(runId, 'pass', 'hello:42').forEach(socket.write);
    await socket.flush();
    await socket.close();
  } else {
    final journal = File('\$sdmc/ctr-runtime.log');
    journal.writeAsStringSync(
      run('0' * 32, 'fail', 'older run').join(),
      mode: FileMode.append,
      flush: true,
    );
    journal.writeAsStringSync(
      run(runId, '$outcome', 'from the journal').join(),
      mode: FileMode.append,
      flush: true,
    );
  }
  // Azahar returns to its game list and stays open.
  await Future<void>.delayed(const Duration(minutes: 5));
}
''';
