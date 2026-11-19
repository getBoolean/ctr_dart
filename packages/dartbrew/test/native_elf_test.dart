import 'dart:io';
import 'dart:typed_data';
import 'package:dartbrew/src/targets/ctr/native_elf.dart';
import 'package:test/test.dart';

import 'support/elf_fixture.dart';

void main() {
  test('rejects data that is not a linked ARM ELF image', () {
    expect(() => encode3dsx(Uint8List(64)), throwsFormatException);
  });

  test('encodes cross-segment addresses and relocation runs', () {
    final bytes = linkedElfFixture();
    final result = ByteData.sublistView(encode3dsx(bytes));
    expect(result.lengthInBytes, 80);
    expect(result.getUint32(0, Endian.little), 0x58534433);
    expect(result.getUint32(40, Endian.little), 1);
    expect(result.getUint32(44, Endian.little), 1);
    expect(result.getUint32(60, Endian.little), 0);
    expect(result.getUint32(64, Endian.little), 0);
    expect(result.getUint16(72, Endian.little), 0);
    expect(result.getUint16(74, Endian.little), 1);
    expect(result.getUint16(76, Endian.little), 1);
    expect(result.getUint16(78, Endian.little), 1);
  });

  group('with SMDH metadata', () {
    final smdh = Uint8List(0x36c0)..setAll(0, 'SMDH'.codeUnits);

    test('declares the extended header and points at the SMDH', () {
      final bytes = encode3dsx(linkedElfFixture(), smdh: smdh);
      final header = ByteData.sublistView(bytes);
      expect(header.getUint32(0, Endian.little), 0x58534433);
      expect(header.getUint16(4, Endian.little), 44);
      expect(header.getUint16(6, Endian.little), 8);
      final offset = header.getUint32(32, Endian.little);
      expect(header.getUint32(36, Endian.little), 0x36c0);
      expect(header.getUint32(40, Endian.little), 0, reason: 'no RomFS');
      expect(offset + 0x36c0, bytes.length);
      expect(String.fromCharCodes(bytes.sublist(offset, offset + 4)), 'SMDH');
    });

    test('keeps every section and relocation byte-identical', () {
      final plain = encode3dsx(linkedElfFixture());
      final extended = encode3dsx(linkedElfFixture(), smdh: smdh);
      expect(extended.sublist(0, 4), plain.sublist(0, 4));
      // The basic header fields after the header size match.
      expect(extended.sublist(6, 32), plain.sublist(6, 32));
      // Relocation headers, sections and relocation tables follow the
      // header unchanged, and the SMDH follows them.
      expect(extended.sublist(44, extended.length - 0x36c0), plain.sublist(32));
    });
  });

  test('matches the qualified converter on the same real ELF', () {
    final directory = Directory(
      Platform.environment['CTR_NATIVE_ELF_FIXTURE']!,
    );
    final elf = File('${directory.path}/application.elf').readAsBytesSync();
    final expected = File(
      '${directory.path}/application.3dsx',
    ).readAsBytesSync();
    final actual = encode3dsx(elf);
    expect(actual, orderedEquals(expected));
  }, skip: !Platform.environment.containsKey('CTR_NATIVE_ELF_FIXTURE'));
}
