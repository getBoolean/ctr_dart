import 'dart:async';

import 'package:test/test.dart';
import 'package:test_api/backend.dart';

Future<void> main() async {
  final declarer = Declarer();
  await runZoned(
    () => declarer.declare(() {
      test('passes', () => expect(1 + 1, 2));
      test('fails', () => expect(1, 2));
    }),
    zoneValues: {#test.declarer: declarer},
  );
  final suite = Suite(
    declarer.build(),
    SuitePlatform(Runtime.vm),
    path: 'probe',
  );
  for (final entry in suite.group.entries) {
    if (entry is! Test) continue;
    final live = (entry as LocalTest).load(suite);
    var errored = false;
    var failed = false;
    live.onError.listen((e) {
      if (e.error is TestFailure) {
        failed = true;
      } else {
        errored = true;
      }
    });
    try {
      await Invoker.guard(live.run);
    } catch (_) {
      errored = true;
    }
    final outcome = errored ? 'error' : (failed ? 'failed' : 'passed');
    print('probe:${entry.name}:$outcome');
  }
  print('probe:done');
}
