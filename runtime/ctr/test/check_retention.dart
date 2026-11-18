// Inspect generated AOT kernel; this does not execute or qualify an AOT image.
import 'dart:io';
import 'package:kernel/ast.dart';
import 'package:kernel/binary/ast_from_binary.dart';

void main(List<String> args) {
  final component = Component();
  BinaryBuilder(File(args.single).readAsBytesSync()).readComponent(component);
  final hooks = component.libraries.singleWhere(
    (library) => library.importUri.toString() == 'dart:_ctr',
  );
  final names = hooks.procedures.map((procedure) => procedure.name.text).toSet();
  for (final name in [
    '_installHooks',
    '_getPrintClosure',
    '_schedule',
    '_clock',
    '_print',
  ]) {
    if (!names.contains(name)) throw StateError('Missing retained hook $name');
  }
  print('Private hooks and native references retained in AOT kernel');
}
