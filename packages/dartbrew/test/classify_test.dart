import 'package:dartbrew/src/test_runner/classify.dart';
import 'package:test/test.dart';

void main() {
  final cases = {
    "Failed to resolve native function 'File_Open' in '_File._open'":
        'file I/O',
    "Invalid argument(s): native function 'Directory_Exists' (1 arguments) "
            'cannot be found':
        'file I/O',
    "Failed to resolve native function 'IOService_NewServicePort' in "
            "'_IOService._newServicePort'":
        'file I/O',
    "Failed to resolve native function 'Socket_CreateConnect' in "
            "'_NativeSocket.createConnect'":
        'sockets',
    "Failed to resolve native function 'InternetAddress_Parse' in "
            "'_InternetAddress._parse'":
        'sockets',
    "Failed to resolve native function 'Process_Start' in "
            "'_ProcessImpl._startNative'":
        'processes',
    "Failed to resolve native function 'Process_Exit' in '_ProcessUtils._exit'":
        'stdout, stdin and exit()',
    "Failed to resolve native function 'File_GetStdioHandleType' in "
            "'_StdIOUtils._getStdioHandleType'":
        'stdout, stdin and exit()',
    'IsolateSpawnException: Unable to spawn isolate: no isolate group':
        'isolates',
    "Invalid argument(s): Failed to load dynamic library 'libx.so'": 'FFI',
    "Unsupported operation: Can't connect to the test runner.\n"
            'spawnHybridUri() is currently only supported within "dart test".':
        'hybrid tests (spawnHybridUri and spawnHybridCode)',
    // The launcher's dart:io fallback resolver (runtime/ctr/source/
    // unsupported.cc) throws UnsupportedError naming the native.
    'Unsupported operation: Namespace_GetDefault is not supported on CTR '
            '(dart:io)':
        'file I/O',
    'Unsupported operation: Platform_OperatingSystem is not supported on '
            'CTR (dart:io)\n#0      _ProcessImpl._start':
        'processes',
    'Unsupported operation: Platform_NumberOfProcessors is not supported on '
            'CTR (dart:io)':
        'platform information (Platform)',
    'Unsupported operation: Platform_GetVersion is not supported on CTR '
            '(dart:io)\n#0      _HttpClient._openUrl':
        'sockets',
    'SocketException: Failed host lookup\n'
            '#0      _NativeSynchronousSocket.lookup':
        'sockets',
    'Unsupported operation: Foo_Bar is not supported on CTR (dart:io)':
        'dart:io',
  };
  cases.forEach((text, area) {
    test('"${text.split('\n').first}" is $area', () {
      expect(classifyUnsupported(text)?.name, area);
    });
  });

  test('the message names the area and the target', () {
    expect(
      classifyUnsupported("native function 'File_Open'")!.message,
      'file I/O is not supported on CTR',
    );
  });

  test('ordinary failures are not attributed to an area', () {
    expect(classifyUnsupported('Expected: <8>\n  Actual: <7>'), isNull);
    expect(classifyUnsupported('Bad state: boom'), isNull);
    expect(classifyUnsupported('lost connection'), isNull);
  });
}
