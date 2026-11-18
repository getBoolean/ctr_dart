// Producer compiles this driver into the SDK's native ctr-kernel executable.
import 'dart:io';
import 'package:kernel/ast.dart';
import 'package:kernel/binary/ast_from_binary.dart';
import 'package:vm/kernel_front_end.dart' show createCompilerArgParser, runCompiler;

Future<void> main(List<String> arguments) async {
  final parser = createCompilerArgParser();
  final options = parser.parse(arguments);
  exitCode = await runCompiler(options, 'ctr-kernel --platform <SDK platform> --output <kernel> <entrypoint>');
  if (exitCode != 0) return;
  final component = Component();
  BinaryBuilder(File(options.option('output')!).readAsBytesSync()).readComponent(component);
  final hooks = component.libraries.singleWhere((library) => library.importUri.toString() == 'dart:_ctr');
  final names = hooks.procedures.map((procedure) => procedure.name.text).toSet();
  for (final required in ['_installHooks', '_getPrintClosure', '_schedule', '_clock', '_print']) {
    if (!names.contains(required)) throw StateError('Missing retained CTR hook: $required');
  }
}
