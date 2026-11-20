import 'package:path/path.dart' as p;

/// [path] relative to [from], with `/` separators on every host.
String posixRelative(String path, {required String from}) =>
    p.posix.joinAll(p.split(p.relative(path, from: from)));
