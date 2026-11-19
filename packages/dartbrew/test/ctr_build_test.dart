import 'dart:io';

import 'package:args/command_runner.dart';
import 'package:dartbrew/src/targets/ctr/build.dart';
import 'package:path/path.dart' as p;
import 'package:test/test.dart';

void main() {
  test('metadata assembly has exactly the native Program fields', () {
    final assembly = programAssembly('jit', 'app', 'a' * 64, 'b' * 64, 123);
    expect(assembly, contains('.word 0, 0, ctr_kernel, 123'));
    expect(assembly, contains('.size ctr_program, 32'));
    expect(
      assembly,
      contains('.word ctr_fixture, ctr_mode, ctr_compatibility, ctr_build_id'),
    );
  });

  test('missing SDK cannot modify the project or output', () async {
    final owner = Directory.systemTemp.createTempSync('dartbrew-owner-');
    addTearDown(() => owner.deleteSync(recursive: true));
    final entry = File(p.join(owner.path, 'main.dart'))
      ..writeAsStringSync('void main() {}');
    final runner = CommandRunner<int>('dartbrew', '')
      ..addCommand(BuildCommand());
    await expectLater(
      runner.run([
        'build',
        entry.path,
        '--sdk',
        p.join(owner.path, 'missing'),
        '--output',
        p.join(owner.path, 'output'),
      ]),
      throwsA(isA<FileSystemException>()),
    );
    expect(entry.readAsStringSync(), 'void main() {}');
    expect(owner.listSync().map((f) => f.path), [entry.path]);
  });
}
