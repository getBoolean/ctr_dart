import 'package:image/image.dart';

/// The built-in 48x48 app icon used when a project names none: a white
/// diamond on a solid teal background, drawn in code.
Image defaultIcon() {
  final icon = Image(width: 48, height: 48);
  for (final pixel in icon) {
    // Distance from the centre between pixels 23 and 24.
    final distance = (pixel.x * 2 - 47).abs() + (pixel.y * 2 - 47).abs();
    if (distance <= 33) {
      pixel.setRgb(255, 255, 255);
    } else if (distance <= 39) {
      pixel.setRgb(178, 223, 219);
    } else {
      pixel.setRgb(0, 121, 107);
    }
  }
  return icon;
}
