"""Opt-in real host VM integration; never represents execution on CTR."""
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('runtime_results', ROOT / 'results.py')
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)


@unittest.skipUnless(os.environ.get('CTR_HOST_VM'), 'set CTR_HOST_VM, CTR_TEST_SDK and CTR_TEST_PLATFORM for real VM checks')
class HostVMTest(unittest.TestCase):
    def run_program(self, body, stop=False, platform=None):
        sdk = Path(os.environ['CTR_TEST_SDK'])
        with tempfile.TemporaryDirectory(prefix='ctr-async-', dir=os.environ.get('CTR_TEST_TMP')) as directory:
            directory = Path(directory)
            source = directory / 'application.dart'
            source.write_text("import 'dart:async';\n" + body)
            kernel = directory / 'application.dill'
            subprocess.run([str(sdk / 'tools/sdks/dart-sdk/bin/dart'),
                            str(sdk / 'pkg/vm/bin/gen_kernel.dart'),
                            '--platform=' + str(platform or os.environ['CTR_TEST_PLATFORM']),
                            '--output=' + str(kernel), str(source)], check=True, timeout=180)
            identity = dict(schema=1, run_id=uuid.uuid4().hex, fixture='async', mode='jit',
                            compatibility='a' * 64, artifact_sha256='a' * 64,
                            build_id='a' * 64, environment='host')
            config = directory / 'run.cfg'
            config.write_text(''.join(f'{key}={identity[key]}\n' for key in results.KEYS))
            journal = directory / 'journal.log'
            command = [os.environ['CTR_HOST_VM'], str(kernel), str(config), str(journal)]
            if stop:
                command.append('stop-on-input')
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            try:
                if stop:
                    # Stop only after a real periodic callback has reached stdout.
                    deadline = time.monotonic() + 20
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
                            self.fail('VM did not deliver a periodic callback before the hang deadline')
                        line = os.read(process.stdout.fileno(), 65536).decode()
                        if not line:
                            self.fail('VM exited before periodic callback: ' + process.stderr.read())
                        if '"text":"periodic"' in line:
                            process.stdin.write('\n')
                            process.stdin.flush()
                            break
                stdout, stderr = process.communicate(timeout=20)
                self.assertIn(process.returncode, (0, 1, 2), (stdout, stderr))
                value = results.validate(journal.read_text(), identity)
                self.assertNotIn('reason', value)
                return value, process.returncode
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
                for stream in (process.stdin, process.stdout, process.stderr):
                    stream.close()

    def test_delayed_microtasks_and_timer_order(self):
        value, code = self.run_program('''
void main(List<String> args) {
  if (args.isNotEmpty) throw StateError('unexpected arguments');
  print('main');
  scheduleMicrotask(() => print('microtask'));
  Timer(Duration.zero, () => print('zero-first'));
  Timer(Duration.zero, () => print('zero-second'));
  final cancelled = Timer(const Duration(days: 1), () => throw StateError('cancelled'));
  Timer(const Duration(milliseconds: 1), () { cancelled.cancel(); print('delayed'); });
}
''')
        self.assertEqual(code, 0)
        self.assertEqual(value['output'], ['main', 'microtask', 'zero-first', 'zero-second', 'delayed'])

    def test_cancel_last_periodic_allows_exit(self):
        value, code = self.run_program('''
void main() {
  Timer.periodic(const Duration(milliseconds: 1), (timer) {
    print('tick'); timer.cancel();
  });
}
''')
        self.assertEqual((code, value['output']), (0, ['tick']))

    def test_uncancelled_periodic_requires_explicit_stop(self):
        value, code = self.run_program('''
void main() {
  var first = true;
  Timer.periodic(const Duration(milliseconds: 1), (timer) {
    if (first) { first = false; print('periodic'); }
  });
}
''', stop=True)
        self.assertEqual((code, value['outcome']), (2, 'incomplete'))
        self.assertEqual(value['output'], ['periodic'])

    def test_async_error_has_stack(self):
        value, code = self.run_program('''
void main() {
  Timer.run(() => throw StateError('async failure'));
}
''')
        self.assertEqual((code, value['outcome']), (1, 'fail'))
        self.assertIn('async failure', '\n'.join(value['output']))
        self.assertIn('application.dart', '\n'.join(value['output']))

    def test_missing_private_hooks_cleans_partial_bootstrap(self):
        # The SDK's ordinary VM platform has no private CTR library.
        platform = os.environ.get('CTR_TEST_BASE_PLATFORM')
        if not platform:
            self.skipTest('set CTR_TEST_BASE_PLATFORM to the same-source ordinary VM platform')
        value, code = self.run_program('void main() {}', platform=platform)
        self.assertEqual((code, value['outcome']), (1, 'fail'))
        self.assertIn('dart:_ctr', '\n'.join(value['output']))
