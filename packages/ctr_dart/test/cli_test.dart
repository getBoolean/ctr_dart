import 'dart:io';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

final hostCli = File('bin/ctr.dart').absolute.path;
Future<ProcessResult> invoke(List<String> args) =>
    Process.run(Platform.resolvedExecutable, [hostCli, ...args]);

void main() {
  test('native CLI help and argument errors need no installed SDK', () async {
    final help = await invoke(['--help']);
    expect(help.exitCode, 0);
    expect(help.stdout, contains('build'));
    expect(help.stdout, contains('doctor'));
    expect(help.stdout, isNot(contains('setup')));
    expect(help.stderr, isEmpty);
    final invalid = await invoke(['build']);
    expect(invalid.exitCode, 64);
    expect(invalid.stdout, isEmpty);
  });

  test('missing SDK cannot modify the project or output', () async {
    final owner = Directory.systemTemp.createTempSync('ctr-owner-');
    addTearDown(() => owner.deleteSync(recursive: true));
    final entry = File(p.join(owner.path, 'main.dart'))
      ..writeAsStringSync('void main() {}');
    final result = await invoke([
      'build',
      entry.path,
      '--sdk',
      p.join(owner.path, 'missing'),
      '--output',
      p.join(owner.path, 'output'),
    ]);
    expect(result.exitCode, isNot(0));
    expect(entry.readAsStringSync(), 'void main() {}');
    expect(owner.listSync().map((f) => f.path), [entry.path]);
  });
}
