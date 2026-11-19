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
