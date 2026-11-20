import 'dart:io';
import 'dart:typed_data';

import 'package:image/image.dart';
import 'package:path/path.dart' as p;
import 'package:yaml/yaml.dart';

import 'default_icon.dart';

/// The title, description, author and icon Homebrew Launcher shows for an app.
final class AppMetadata {
  final String title, description, author;

  /// The icon image, any size; `null` uses [defaultIcon].
  final Image? icon;

  const AppMetadata({
    required this.title,
    required this.description,
    required this.author,
    required this.icon,
  });
}

/// Reads [AppMetadata] for the project in [project].
///
/// The title and description come from the pubspec `name` and
/// `description`; a top-level `dartbrew:` map can override `title`,
/// `description`, `author` and `icon` (a PNG path relative to [project]).
/// Without a pubspec name the title is [fallbackTitle].
AppMetadata readAppMetadata(String project, {required String fallbackTitle}) {
  final file = File(p.join(project, 'pubspec.yaml'));
  final pubspec = file.existsSync()
      ? loadYaml(file.readAsStringSync(), sourceUrl: file.uri)
      : null;
  final root = pubspec is YamlMap ? pubspec : YamlMap();
  final overrides = root['dartbrew'] ?? YamlMap();
  if (overrides is! YamlMap) {
    throw FormatException('`dartbrew` in ${file.path} must be a map.');
  }
  String? text(YamlMap map, String key) => switch (map[key]) {
    null => null,
    final String value => value,
    final num value => '$value',
    _ => throw FormatException('`$key` in ${file.path} must be a string.'),
  };
  final iconPath = text(overrides, 'icon');
  Image? icon;
  if (iconPath != null) {
    final path = p.join(project, iconPath);
    final bytes = File(path).existsSync()
        ? File(path).readAsBytesSync()
        : throw FileSystemException('App icon not found', path);
    icon =
        decodePng(bytes) ??
        (throw FormatException('App icon is not a PNG image: $path'));
  }
  return AppMetadata(
    title: text(overrides, 'title') ?? text(root, 'name') ?? fallbackTitle,
    description:
        text(overrides, 'description') ?? text(root, 'description') ?? '',
    author: text(overrides, 'author') ?? '',
    icon: icon,
  );
}

/// The SMDH for the project in [project]; see [readAppMetadata] and
/// [encodeSmdh].
Uint8List projectSmdh(
  String project, {
  required String fallbackTitle,
  StringSink? warnings,
}) => encodeSmdh(
  readAppMetadata(project, fallbackTitle: fallbackTitle),
  warnings: warnings,
);

/// Encodes [metadata] as a 0x36C0-byte SMDH block.
///
/// The strings are written as UTF-16LE into every language slot; strings
/// longer than their field (minus a terminator) are truncated and a warning
/// is written to [warnings]. The icon is scaled to 24x24 and 48x48.
Uint8List encodeSmdh(AppMetadata metadata, {StringSink? warnings}) {
  final smdh = Uint8List(0x36c0);
  final data = ByteData.sublistView(smdh)
    ..setUint32(0, 0x48444d53, Endian.little) // "SMDH"
    ..setUint32(0x2018, 0x7fffffff, Endian.little) // region free
    ..setUint32(0x2028, 0x0001 | 0x0004 | 0x0100, Endian.little);
  void field(int offset, int size, String name, String value) {
    var units = value.codeUnits;
    final limit = size ~/ 2 - 1;
    if (units.length > limit) {
      var end = limit;
      if (units[end - 1] >= 0xd800 && units[end - 1] < 0xdc00) end--;
      units = units.sublist(0, end);
      warnings?.writeln(
        'Warning: the app $name is longer than $limit UTF-16 code units '
        'and was truncated.',
      );
    }
    for (var language = 0; language < 16; language++) {
      final start = 8 + language * 0x200 + offset;
      for (var i = 0; i < units.length; i++) {
        data.setUint16(start + i * 2, units[i], Endian.little);
      }
    }
  }

  field(0, 0x80, 'title', metadata.title);
  field(0x80, 0x100, 'description', metadata.description);
  field(0x180, 0x80, 'author', metadata.author);
  final icon = metadata.icon ?? defaultIcon();
  smdh
    ..setAll(0x2040, encodeIcon(icon, 24))
    ..setAll(0x24c0, encodeIcon(icon, 48));
  return smdh;
}

/// [image] scaled to [size]x[size] and encoded as little-endian RGB565 in
/// 8x8 tiles, row-major across tiles and Z-order within each tile.
/// Transparent pixels are blended onto black.
Uint8List encodeIcon(Image image, int size) {
  final scaled = image.width == size && image.height == size
      ? image
      : copyResize(
          image,
          width: size,
          height: size,
          interpolation: Interpolation.average,
        );
  final output = ByteData(size * size * 2);
  var index = 0;
  for (var tileY = 0; tileY < size; tileY += 8) {
    for (var tileX = 0; tileX < size; tileX += 8) {
      for (var i = 0; i < 64; i++) {
        // De-interleave the Morton index: even bits are x, odd bits are y.
        final x = tileX + (i & 1 | (i >> 1) & 2 | (i >> 2) & 4);
        final y = tileY + ((i >> 1) & 1 | (i >> 2) & 2 | (i >> 3) & 4);
        final pixel = scaled.getPixel(x, y);
        final alpha = pixel.aNormalized;
        int channel(num value, int bits) =>
            (value * alpha * 255).round().clamp(0, 255) >> (8 - bits);
        final rgb =
            channel(pixel.rNormalized, 5) << 11 |
            channel(pixel.gNormalized, 6) << 5 |
            channel(pixel.bNormalized, 5);
        output.setUint16(index, rgb, Endian.little);
        index += 2;
      }
    }
  }
  return output.buffer.asUint8List();
}
