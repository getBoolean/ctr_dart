import 'dart:typed_data';

/// A small linked ARM ELF image with code, read-only and data segments and
/// one relocation section, laid out the way this SDK's linker emits them.
Uint8List linkedElfFixture() {
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
  return bytes;
}
