import 'dart:io';
import 'dart:typed_data';
import 'package:ctr_dart/src/native_elf.dart';
import 'package:test/test.dart';

void main() {
  test('rejects data that is not a linked ARM ELF image', () {
    expect(() => encode3dsx(Uint8List(64)), throwsFormatException);
  });

  test('encodes cross-segment addresses and relocation runs', () {
    final bytes = Uint8List(0x3100 + 5 * 40);
    final e = ByteData.sublistView(bytes);
    void w(int at, int value) => e.setUint32(at, value, Endian.little);
    void h(int at, int value) => e.setUint16(at, value, Endian.little);
    bytes.setRange(0, 7, [0x7f, 69, 76, 70, 1, 1, 1]);
    h(16, 2);
    h(18, 40);
    w(24, 0x100000);
    w(28, 52);
    w(32, 0x3100);
    h(42, 32);
    h(44, 3);
    h(46, 40);
    h(48, 5);
    for (var i = 0; i < 3; i++) {
      final at = 52 + i * 32;
      w(at, 1);
      w(at + 4, 0x1000 * (i + 1));
      w(at + 8, 0x100000 + i * 0x1000);
      w(at + 16, i == 1 ? 8 : 4);
      w(at + 20, i == 0 ? 4 : 8);
      w(at + 24, [5, 4, 6][i]);
      final sh = 0x3100 + (i + 1) * 40;
      w(sh + 4, 1);
      w(sh + 8, i == 0 ? 6 : 3);
      w(sh + 12, 0x100000 + i * 0x1000);
      w(sh + 16, 0x1000 * (i + 1));
      w(sh + 20, i == 1 ? 8 : 4);
    }
    final rel = 0x3100 + 4 * 40;
    w(rel + 4, 9);
    w(rel + 16, 0x3050);
    w(rel + 20, 16);
    w(rel + 28, 2);
    w(rel + 36, 8);
    w(0x1000, 0xe12fff1e);
    w(0x2000, 0x100000);
    w(0x2004, 0xffffeffc);
    w(0x3050, 0x101000);
    w(0x3054, 2);
    w(0x3058, 0x101004);
    w(0x305c, 3);
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
