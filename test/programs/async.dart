import 'dart:async';

Future<void> main(List<String> arguments) async {
  final events = <String>[];
  scheduleMicrotask(() => events.add('microtask'));
  Timer(Duration.zero, () => events.add('zero'));
  final cancelled = Timer(const Duration(days: 1), () {
    throw StateError('cancelled timer fired');
  });
  Timer(const Duration(milliseconds: 5), () {
    cancelled.cancel();
    events.add('delayed');
  });
  await Future<void>.delayed(const Duration(milliseconds: 20));
  if (events.join(',') != 'microtask,zero,delayed') {
    throw StateError('unexpected async order: $events');
  }
  print('async:pass');
}
