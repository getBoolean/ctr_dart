import 'dart:convert';

/// One line of the app's output that starts with `CTR_RUNTIME `.
sealed class RuntimeLine {
  const RuntimeLine();
}

/// A prefixed line whose payload is a JSON object.
final class RuntimeRecord extends RuntimeLine {
  const RuntimeRecord(this.fields);

  final Map<String, Object?> fields;
}

/// A prefixed line whose payload is not a JSON object.
final class MalformedRecord extends RuntimeLine {
  const MalformedRecord();
}

/// Splits a byte stream into lines and parses the `CTR_RUNTIME ` ones.
///
/// Chunks may end anywhere, including inside a line or a multi-byte
/// character. Lines end at LF, a trailing CR is dropped, and lines without
/// the prefix (keepalive blanks, boot noise) are ignored.
final class RuntimeLineParser {
  static const prefix = 'CTR_RUNTIME ';

  final _pending = <int>[];

  /// Consumes [chunk] and returns the records of the lines it completed.
  List<RuntimeLine> feed(List<int> chunk) {
    final lines = <RuntimeLine>[];
    var start = 0;
    for (var i = 0; i < chunk.length; i++) {
      if (chunk[i] != 0x0A) continue;
      _pending.addAll(chunk.getRange(start, i));
      start = i + 1;
      _emit(lines);
    }
    _pending.addAll(chunk.getRange(start, chunk.length));
    return lines;
  }

  /// Returns the record of a final line that has no line ending, if any.
  List<RuntimeLine> close() {
    final lines = <RuntimeLine>[];
    _emit(lines);
    return lines;
  }

  void _emit(List<RuntimeLine> lines) {
    if (_pending.isNotEmpty && _pending.last == 0x0D) _pending.removeLast();
    final text = utf8.decode(_pending, allowMalformed: true);
    _pending.clear();
    if (!text.startsWith(prefix)) return;
    try {
      final record = jsonDecode(text.substring(prefix.length));
      lines.add(
        record is Map<String, Object?>
            ? RuntimeRecord(record)
            : const MalformedRecord(),
      );
    } on FormatException {
      lines.add(const MalformedRecord());
    }
  }
}
