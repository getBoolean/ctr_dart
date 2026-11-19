import 'dart:io';

import 'package:dartbrew/src/cli.dart';

Future<void> main(List<String> arguments) async {
  exitCode = await runCli(arguments);
}
