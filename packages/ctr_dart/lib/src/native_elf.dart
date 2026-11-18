import 'dart:collection';
import 'dart:typed_data';

int _page(int size) => (size + 4095) & ~4095;

class _Segment {
  final int address, memorySize;
  final Uint8List bytes;
  final relocations = [SplayTreeSet<int>(), SplayTreeSet<int>()];
  _Segment(this.address, this.memorySize, this.bytes);
  bool contains(int value) => value >= address && value < address + memorySize;
}

/// Convert this SDK's statically linked ARM ELF layout into a basic 3DSX image.
/// Addresses use the 3DSX logical page layout; relative subtype 1 denotes PREL31.
Uint8List encode3dsx(Uint8List elf) {
  final reader = ByteData.sublistView(elf);
  void range(int offset, int size) {
    if (offset < 0 || size < 0 || offset + size > elf.length) {
      throw const FormatException(
        'ELF field or data extends outside the file.',
      );
    }
  }

  int u16(int at) {
    range(at, 2);
    return reader.getUint16(at, Endian.little);
  }

  int u32(int at) {
    range(at, 4);
    return reader.getUint32(at, Endian.little);
  }

  range(0, 52);
  if (u32(0) != 0x464c457f ||
      elf[4] != 1 ||
      elf[5] != 1 ||
      u16(16) != 2 ||
      u16(18) != 40) {
    throw const FormatException(
      'Expected a linked little-endian ARM ELF32 image.',
    );
  }
  final segments = <_Segment>[];
  final programOffset = u32(28), programSize = u16(42);
  if (programSize < 32)
    throw const FormatException('Invalid ELF program headers.');
  final loadFlags = <int>[];
  for (var i = 0; i < u16(44); i++) {
    final at = programOffset + i * programSize;
    range(at, 32);
    if (u32(at) != 1) continue;
    final offset = u32(at + 4), size = u32(at + 16), memory = u32(at + 20);
    range(offset, size);
    if (size > memory)
      throw const FormatException('ELF file data exceeds segment memory.');
    segments.add(
      _Segment(u32(at + 8), memory, elf.sublist(offset, offset + size)),
    );
    loadFlags.add(u32(at + 24));
  }
  if (segments.length != 3 ||
      loadFlags[0] != 5 ||
      loadFlags[1] != 4 ||
      loadFlags[2] != 6) {
    throw const FormatException(
      'Expected code, read-only and writable load segments.',
    );
  }
  final base = segments.first.address;
  var end = base;
  for (var i = 0; i < segments.length; i++) {
    final segment = segments[i];
    if (segment.address != end ||
        (i != 2 && segment.bytes.length != segment.memorySize)) {
      throw const FormatException(
        'ELF segments do not match the SDK page layout.',
      );
    }
    end += _page(segment.memorySize);
  }
  if (u32(24) != base || end - base >= 0x10000000) {
    throw const FormatException(
      'ELF entry or size is not representable by this 3DSX layout.',
    );
  }
  final sectionOffset = u32(32), sectionSize = u16(46), sectionCount = u16(48);
  if (sectionSize < 40 || sectionCount == 0) {
    throw const FormatException('ELF relocation sections are required.');
  }
  range(sectionOffset, sectionSize * sectionCount);
  for (var i = 0; i < sectionCount; i++) {
    final section = sectionOffset + i * sectionSize;
    if (u32(section + 4) != 9) continue;
    final targetSection = u32(section + 28);
    if (targetSection >= sectionCount)
      throw const FormatException('Invalid ELF relocation section.');
    if (u32(sectionOffset + targetSection * sectionSize + 8) & 2 == 0) continue;
    final offset = u32(section + 16),
        size = u32(section + 20),
        stride = u32(section + 36);
    if (stride != 8 || size % stride != 0)
      throw const FormatException('Invalid ARM REL table.');
    range(offset, size);
    for (var entry = offset; entry < offset + size; entry += stride) {
      final place = u32(entry), type = u32(entry + 4) & 255;
      if (const {0, 1, 10, 27, 28, 29, 30, 40, 108}.contains(type)) continue;
      final source = segments
          .where((segment) => segment.contains(place))
          .firstOrNull;
      // --emit-relocs can retain unwind records for discarded input sections.
      if (source == null) continue;
      if (place % 4 != 0 || place + 4 > source.address + source.bytes.length) {
        throw const FormatException(
          'ARM relocation is outside initialized aligned image data.',
        );
      }
      final word = place - source.address;
      final data = ByteData.sublistView(source.bytes);
      final value = data.getUint32(word, Endian.little);
      final absolute = type == 2 || type == 38;
      final relative = const {3, 25, 42, 107}.contains(type);
      if (!absolute && !relative)
        throw FormatException('Unsupported ARM relocation: $type');
      var target = value;
      if (relative) {
        var displacement = value;
        if (type == 42) {
          displacement = value.toSigned(31);
        }
        target = (place + displacement) & 0xffffffff;
      }
      if (target < base || target > end) continue;
      if (relative && source.contains(target)) continue;
      var encoded = target - base;
      if (type == 42) encoded |= 0x10000000;
      data.setUint32(word, encoded, Endian.little);
      source.relocations[absolute ? 0 : 1].add(word ~/ 4);
    }
  }
  final tables = <Uint8List>[];
  for (final segment in segments) {
    for (final positions in segment.relocations) {
      final output = BytesBuilder(copy: false);
      final words = positions.toList();
      var cursor = 0, index = 0;
      void emit(int skip, int count) {
        final entry = ByteData(4)
          ..setUint16(0, skip, Endian.little)
          ..setUint16(2, count, Endian.little);
        output.add(entry.buffer.asUint8List());
      }

      while (index < words.length) {
        final start = words[index];
        while (start - cursor > 65535) {
          emit(65535, 0);
          cursor += 65535;
        }
        var count = 1;
        while (index + count < words.length &&
            count < 65535 &&
            words[index + count] == start + count) {
          count++;
        }
        emit(start - cursor, count);
        cursor = start + count;
        index += count;
      }
      tables.add(output.takeBytes());
    }
  }
  final header = ByteData(56)
    ..setUint32(0, 0x58534433, Endian.little)
    ..setUint16(4, 32, Endian.little)
    ..setUint16(6, 8, Endian.little)
    ..setUint32(16, segments[0].memorySize, Endian.little)
    ..setUint32(20, segments[1].memorySize, Endian.little)
    ..setUint32(24, segments[2].memorySize, Endian.little)
    ..setUint32(
      28,
      segments[2].memorySize - segments[2].bytes.length,
      Endian.little,
    );
  for (var i = 0; i < tables.length; i++) {
    header.setUint32(32 + i * 4, tables[i].length ~/ 4, Endian.little);
  }
  final output = BytesBuilder(copy: false)
    ..add(header.buffer.asUint8List())
    ..add(segments[0].bytes)
    ..add(segments[1].bytes)
    ..add(segments[2].bytes);
  for (final table in tables) {
    output.add(table);
  }
  return output.takeBytes();
}
