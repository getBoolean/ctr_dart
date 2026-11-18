import 'dart:io';
import 'package:ctr_dart/src/native_sdk.dart';

Future<void> main(List<String> arguments) async {
  exitCode = await runNativeCli(arguments);
}
