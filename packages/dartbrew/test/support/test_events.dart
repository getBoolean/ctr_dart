import 'dart:convert';

import 'package:dartbrew/src/test_runner/events.dart';

/// Builds the marker lines a generated test entrypoint prints, in the shape
/// recorded from a host run of one (see `test_entrypoint_test.dart`).
final class RecordedStream {
  final lines = <String>[];
  int _id;
  var _time = 0;

  /// [firstId] is the entrypoint's first event ID.
  RecordedStream({int firstId = 0}) : _id = firstId;

  void _emit(String type, Map<String, Object?> fields) => lines.add(
    '$testEventMarker${jsonEncode({...fields, 'type': type, 'time': _time++})}',
  );

  /// Emits a `suite` event and returns its ID.
  int suite(String path) {
    final id = _id++;
    _emit('suite', {
      'suite': {'id': id, 'platform': 'vm', 'path': path},
    });
    return id;
  }

  void plan(int suite, List<String> names) =>
      _emit(planEventType, {'suiteID': suite, 'tests': names});

  /// Emits a `testStart` event and returns the test's ID.
  int start(int suite, String name) {
    final id = _id++;
    _emit('testStart', {
      'test': {
        'id': id,
        'name': name,
        'suiteID': suite,
        'groupIDs': <int>[],
        'metadata': {'skip': false, 'skipReason': null},
        'line': null,
        'column': null,
        'url': null,
      },
    });
    return id;
  }

  void printed(int test, String message) => _emit('print', {
    'testID': test,
    'messageType': 'print',
    'message': message,
  });

  void error(
    int test,
    String error, {
    bool isFailure = false,
    String stackTrace = '',
  }) => _emit('error', {
    'testID': test,
    'error': error,
    'stackTrace': stackTrace,
    'isFailure': isFailure,
  });

  void testDone(int test, String result, {bool skipped = false}) => _emit(
    'testDone',
    {'testID': test, 'result': result, 'hidden': false, 'skipped': skipped},
  );

  /// Starts and passes a test named [name].
  void pass(int suite, String name) => testDone(start(suite, name), 'success');

  void done() => _emit('done', {});

  /// A stream of [count] passing tests in `test/a_test.dart`.
  static RecordedStream passing(int count) {
    final names = [for (var i = 1; i <= count; i++) 'test $i'];
    final stream = RecordedStream();
    final suite = stream.suite('test/a_test.dart');
    stream.plan(suite, names);
    for (final name in names) {
      stream.pass(suite, name);
    }
    stream.done();
    return stream;
  }

  /// AE3: one pure-logic test and one that reads a file, which fails with
  /// the VM's text for an unresolved `dart:io` native.
  static RecordedStream fileIo() {
    final stream = RecordedStream();
    final suite = stream.suite('test/io_test.dart');
    stream
      ..plan(suite, ['adds', 'reads a file'])
      ..pass(suite, 'adds');
    final reads = stream.start(suite, 'reads a file');
    stream
      ..error(
        reads,
        "Invalid argument(s): native function 'File_Open' (2 arguments) "
        'cannot be found',
        stackTrace:
            'dart:io/file_impl.dart  _File._openSync\n'
            'test/io_test.dart 7:30  main.<fn>',
      )
      ..testDone(reads, 'error')
      ..done();
    return stream;
  }
}
