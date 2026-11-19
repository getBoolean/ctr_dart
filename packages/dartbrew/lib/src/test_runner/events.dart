import 'dart:convert';

/// The prefix of an output line that carries one test event from the
/// generated test entrypoint (see `targets/ctr/test_entrypoint.dart`).
const testEventMarker = 'DARTBREW_TEST ';

/// The device-only event that lists, per suite, the names of the tests the
/// entrypoint is about to run, so the host can report the ones a stopped
/// run never reached. It is never passed on to the JSON reporter.
const planEventType = 'dartbrew.plan';

/// One piece of a test program's output.
sealed class TestOutput {
  const TestOutput();
}

/// A marker line whose payload is a JSON object with a string `type`.
final class TestEvent extends TestOutput {
  final Map<String, Object?> fields;

  const TestEvent(this.fields);

  String get type => fields['type'] as String;
}

/// Any other output line, such as a `print` outside a test.
final class TestText extends TestOutput {
  final String text;

  const TestText(this.text);
}

/// Splits [text], the text of one output record, into lines and parses the
/// marker lines. A marker line whose payload is not a JSON object with a
/// string `type` is kept as plain text.
List<TestOutput> parseTestOutput(String text) => [
  for (final line in const LineSplitter().convert(text)) _parseLine(line),
];

TestOutput _parseLine(String line) {
  if (!line.startsWith(testEventMarker)) return TestText(line);
  try {
    final fields = jsonDecode(line.substring(testEventMarker.length));
    if (fields is Map<String, Object?> && fields['type'] is String) {
      return TestEvent(fields);
    }
  } on FormatException {
    // Kept as text below.
  }
  return TestText(line);
}
