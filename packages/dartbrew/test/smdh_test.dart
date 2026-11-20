import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dartbrew/src/targets/ctr/default_icon.dart';
import 'package:dartbrew/src/targets/ctr/smdh.dart';
import 'package:image/image.dart' as img;
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

const _small = 0x2040, _large = 0x24c0;

String _project({String? pubspec}) {
  final root = Directory.systemTemp.createTempSync('dartbrew-smdh-');
  addTearDown(() => root.deleteSync(recursive: true));
  if (pubspec != null) {
    File(p.join(root.path, 'pubspec.yaml')).writeAsStringSync(pubspec);
  }
  return root.path;
}

/// The UTF-16LE string in the title struct [language] at [field] offset.
String _text(Uint8List smdh, int language, int field, int size) {
  final start = 8 + language * 0x200 + field;
  final units = ByteData.sublistView(smdh, start, start + size);
  final codes = [
    for (var i = 0; i < size; i += 2) units.getUint16(i, Endian.little),
  ];
  final end = codes.indexOf(0);
  return String.fromCharCodes(end < 0 ? codes : codes.sublist(0, end));
}

String _short(Uint8List smdh, [int language = 1]) =>
    _text(smdh, language, 0, 0x80);
String _long(Uint8List smdh, [int language = 1]) =>
    _text(smdh, language, 0x80, 0x100);
String _publisher(Uint8List smdh, [int language = 1]) =>
    _text(smdh, language, 0x180, 0x80);

Uint8List _smdh(String project, {StringSink? warnings}) =>
    projectSmdh(project, fallbackTitle: 'fallback', warnings: warnings);

void main() {
  test('covers AE6: pubspec name and description become the titles', () {
    final smdh = _smdh(
      _project(
        pubspec:
            'name: snake\ndescription: >-\n  Eat the apples and\n'
            '  avoid your tail.\n',
      ),
    );
    expect(smdh.length, 0x36c0);
    expect(ascii.decode(smdh.sublist(0, 4)), 'SMDH');
    for (var language = 0; language < 16; language++) {
      expect(_short(smdh, language), 'snake');
      expect(_long(smdh, language), 'Eat the apples and avoid your tail.');
    }
    expect(_publisher(smdh), '');
    // Region free and visible on the menu.
    final settings = ByteData.sublistView(smdh);
    expect(settings.getUint32(0x2018, Endian.little), 0x7fffffff);
    expect(settings.getUint32(0x2028, Endian.little) & 1, 1);
  });

  test('dartbrew overrides replace the pubspec values', () {
    final smdh = _smdh(
      _project(
        pubspec:
            'name: snake\ndescription: plain\ndartbrew:\n'
            '  title: Snake Deluxe\n  description: Better\n  author: Me\n',
      ),
    );
    expect(_short(smdh), 'Snake Deluxe');
    expect(_long(smdh), 'Better');
    expect(_publisher(smdh), 'Me');
  });

  test('without a pubspec the fallback title is used', () {
    expect(_short(_smdh(_project())), 'fallback');
  });

  test('over-long strings are truncated with a warning', () {
    final warnings = StringBuffer();
    final smdh = _smdh(
      _project(pubspec: 'name: snake\ndartbrew:\n  title: ${'t' * 100}\n'),
      warnings: warnings,
    );
    expect(_short(smdh), 't' * 63);
    expect(smdh.sublist(8 + 0x7e, 8 + 0x80), [0, 0]);
    expect(warnings.toString(), contains('title'));
    expect(warnings.toString(), contains('63'));
  });

  test('truncation does not split a surrogate pair', () {
    final warnings = StringBuffer();
    final title = '${'t' * 62}\u{1F40D}';
    final smdh = encodeSmdh(
      AppMetadata(title: title, description: '', author: '', icon: null),
      warnings: warnings,
    );
    expect(_short(smdh), 't' * 62);
    expect(warnings.toString(), isNotEmpty);
  });

  test('a 64x64 PNG icon is scaled into both tiled RGB565 icons', () {
    final project = _project(
      pubspec: 'name: snake\ndartbrew:\n  icon: art/icon.png\n',
    );
    final red = img.Image(width: 64, height: 64)
      ..clear(img.ColorRgb8(255, 0, 0));
    File(p.join(project, 'art/icon.png'))
      ..createSync(recursive: true)
      ..writeAsBytesSync(img.encodePng(red));
    final smdh = _smdh(project);
    final small = ByteData.sublistView(smdh, _small, _large);
    final large = ByteData.sublistView(smdh, _large, 0x36c0);
    expect(small.lengthInBytes, 0x480);
    expect(large.lengthInBytes, 0x1200);
    for (final icon in [small, large]) {
      for (var i = 0; i < icon.lengthInBytes; i += 2) {
        expect(icon.getUint16(i, Endian.little), 0xf800);
      }
    }
  });

  test('icons are written in 8x8 tiles in Z-order', () {
    final image = img.Image(width: 48, height: 48);
    for (final pixel in image) {
      pixel
        ..r = pixel.x * 4
        ..g = pixel.y * 4
        ..b = 0;
    }
    final icon = ByteData.sublistView(encodeIcon(image, 48));
    int at(int index) => icon.getUint16(index * 2, Endian.little);
    int rgb565(int x, int y) => ((x * 4) >> 3) << 11 | ((y * 4) >> 2) << 5;
    expect(at(0), rgb565(0, 0));
    expect(at(1), rgb565(1, 0));
    expect(at(2), rgb565(0, 1));
    expect(at(3), rgb565(1, 1));
    expect(at(4), rgb565(2, 0));
    expect(at(8), rgb565(0, 2));
    expect(at(63), rgb565(7, 7));
    expect(at(64), rgb565(8, 0));
    expect(at(6 * 64), rgb565(0, 8));
  });

  test('a missing icon fails with an error naming the path', () {
    final project = _project(
      pubspec: 'name: snake\ndartbrew:\n  icon: missing.png\n',
    );
    expect(
      () => _smdh(project),
      throwsA(
        isA<FileSystemException>().having(
          (e) => e.path,
          'path',
          p.join(project, 'missing.png'),
        ),
      ),
    );
  });

  test('a file that is not a PNG fails with an error naming the path', () {
    final project = _project(
      pubspec: 'name: snake\ndartbrew:\n  icon: icon.png\n',
    );
    File(p.join(project, 'icon.png')).writeAsStringSync('not a png');
    expect(
      () => _smdh(project),
      throwsA(
        isA<FormatException>().having(
          (e) => e.message,
          'message',
          contains(p.join(project, 'icon.png')),
        ),
      ),
    );
  });

  test('without an icon override the built-in default icon is used', () {
    final smdh = _smdh(_project(pubspec: 'name: snake\n'));
    final icon = defaultIcon();
    expect(smdh.sublist(_small, _large), encodeIcon(icon, 24));
    expect(smdh.sublist(_large, 0x36c0), encodeIcon(icon, 48));
    // Not a blank image.
    expect(smdh.sublist(_large, 0x36c0).toSet().length, greaterThan(2));
  });

  test('a dartbrew value that is not a map is rejected', () {
    expect(
      () => _smdh(_project(pubspec: 'name: snake\ndartbrew: yes\n')),
      throwsFormatException,
    );
  });
}
