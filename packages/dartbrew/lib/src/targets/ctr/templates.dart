/// The files of a new CTR console-app project, keyed by relative path with
/// `/` separators. Embedded as strings because `dart create` has no
/// extension point.
Map<String, String> ctrTemplate(String name) => {
  'pubspec.yaml':
      '''
name: $name
description: A console app built with dartbrew.
publish_to: none
environment:
  sdk: '>=3.11.0 <4.0.0'
dev_dependencies:
  test: ^1.33.0

# Shown by Homebrew Launcher. Also supported: description, author.
dartbrew:
  title: $name
  # icon: assets/icon.png
''',
  'bin/main.dart':
      '''
import 'package:$name/$name.dart';

void main(List<String> arguments) {
  final value = add(arguments.length, 42);
  print('Hello from $name: \$value');
}
''',
  'lib/$name.dart': '''
/// Adds [left] and [right].
int add(int left, int right) => left + right;
''',
  'test/${name}_test.dart':
      '''
import 'package:test/test.dart';
import 'package:$name/$name.dart';

void main() {
  test('add sums its arguments', () {
    expect(add(2, 40), 42);
  });

  test('add handles negative numbers', () {
    expect(add(-1, 1), 0);
  });
}
''',
  'analysis_options.yaml': '''
analyzer:
  language:
    strict-casts: true
    strict-inference: true
    strict-raw-types: true
''',
  'README.md':
      '''
# $name

A Dart console app for dartbrew.

## Commands

- `dartbrew compile --output build bin/main.dart` builds the app. Copy the
  contents of `build/SDROOT` to the root of the SD card.
- `dartbrew run bin/main.dart` builds the app, sends it to the console and
  prints its output here. On the console, open Homebrew Launcher and press Y
  to start the netloader first.
- `dartbrew test` runs the tests in `test/` on the console.
- `dartbrew devices` lists the devices dartbrew can run on.
- `dart test` runs the same test files on your computer.
- `dartbrew pub get`, `dartbrew analyze` and `dartbrew format .` run the
  bundled Dart tools.

Keep the tests to pure logic so they run in both places.
''',
  '.gitignore': '''
.dart_tool/
build/
''',
};
