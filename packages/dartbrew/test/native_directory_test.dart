import 'dart:io';
import 'dart:isolate';
import 'package:dartbrew/src/native_directory.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

void main() {
  test('exclusive directory creation preserves an existing owner', () {
    final parent = Directory.systemTemp.createTempSync('dartbrew directory ');
    addTearDown(() => parent.deleteSync(recursive: true));
    final path = p.join(parent.path, 'build');
    createDirectoryExclusively(path);
    final owner = File(p.join(path, 'owner'))..writeAsStringSync('keep');
    expect(
      () => createDirectoryExclusively(path),
      throwsA(isA<FileSystemException>()),
    );
    expect(Directory(path).listSync().map((p) => p.path), [owner.path]);
    expect(owner.readAsStringSync(), 'keep');
  });

  test('paths with dot segments reserve their normalized directory', () {
    final parent = Directory.systemTemp.createTempSync(
      'dartbrew directory dots ',
    );
    addTearDown(() => parent.deleteSync(recursive: true));
    Directory(p.join(parent.path, 'sub')).createSync();
    createDirectoryExclusively(p.join(parent.path, '.', 'sub', '..', 'build'));
    expect(Directory(p.join(parent.path, 'build')).existsSync(), isTrue);
    expect(
      () =>
          createDirectoryExclusively(p.join(parent.path, 'sub', '..', 'build')),
      throwsA(isA<FileSystemException>()),
    );
  });

  test('a relative output resolves against the working directory', () {
    final parent = Directory.systemTemp.createTempSync(
      'dartbrew directory rel ',
    );
    final previous = Directory.current;
    addTearDown(() {
      Directory.current = previous;
      parent.deleteSync(recursive: true);
    });
    Directory.current = parent;
    createDirectoryExclusively('./build');
    expect(Directory(p.join(parent.path, 'build')).existsSync(), isTrue);
  });

  test('independent callers cannot both reserve the same directory', () async {
    final parent = Directory.systemTemp.createTempSync(
      'dartbrew directory race ',
    );
    addTearDown(() => parent.deleteSync(recursive: true));
    final path = p.join(parent.path, 'build');
    Future<bool> reserve() => Isolate.run(() {
      try {
        createDirectoryExclusively(path);
        return true;
      } on FileSystemException {
        return false;
      }
    });
    final results = await Future.wait([reserve(), reserve()]);
    expect(results.where((success) => success).length, 1);
    expect(Directory(path).existsSync(), isTrue);
  });
}
