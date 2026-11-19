"""Opt-in real native SDK checks; no fake compiler success paths."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('CTR_NATIVE_SDK'), 'set CTR_NATIVE_SDK to a built native bundle')
class NativeSdkIntegration(unittest.TestCase):
    def setUp(self):
        self.sdk = Path(os.environ['CTR_NATIVE_SDK']).resolve()
        self.cli = self.sdk / ('dartbrew.exe' if os.name == 'nt' else 'dartbrew')
        retained = os.environ.get('CTR_NATIVE_VERIFY_DIR')
        if retained:
            self.project = Path(tempfile.mkdtemp(prefix='ctr native SDK ', dir=retained))
        else:
            self.temporary = tempfile.TemporaryDirectory(prefix='ctr native SDK ')
            self.addCleanup(self.temporary.cleanup)
            self.project = Path(self.temporary.name)
        self.entry = self.project / 'main.dart'
        self.entry.write_text('void main() { print("native:42"); }\n')

    def invoke(self, *args):
        return subprocess.run([str(self.cli), *map(str, args)], cwd=self.project,
                              env=dict(os.environ, PATH=''), text=True, capture_output=True)

    def test_real_aot_and_jit_builds_in_a_path_with_spaces(self):
        hashes = []
        for mode in ('aot', 'jit'):
            with self.subTest(mode=mode):
                output = self.project / mode
                result = self.invoke('compile', self.entry, '--mode', mode, '--output', output)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                artifact = json.loads((output / 'artifact.json').read_text())
                self.assertEqual(artifact['mode'], mode)
                self.assertEqual((output / 'application.3dsx').read_bytes()[:4], b'3DSX')
                run = json.loads((output / 'run.json').read_text())
                self.assertEqual(run['build_id'], artifact['build_id'])
                self.assertEqual(run['artifact_sha256'], artifact['artifact_sha256'])
                self.assertIn('run_id=' + run['run_id'], (output / 'SDROOT/ctr-runtime-run.cfg').read_text())
                self.assertEqual(
                    [line.split('=', 1)[0] for line in (output / 'SDROOT/ctr-runtime-run.cfg').read_text().splitlines()],
                    ['schema', 'run_id', 'fixture', 'mode', 'compatibility',
                     'artifact_sha256', 'build_id', 'environment'])
                commands = json.loads((output / 'work/commands.json').read_text())
                for command in commands:
                    self.assertTrue(Path(command['executable']).is_relative_to(self.sdk))
                hashes.append(artifact['artifact_sha256'])
        self.assertNotEqual(*hashes)

    def test_invalid_dart_is_not_published(self):
        self.entry.write_text('void main( { syntax error\n')
        output = self.project / 'failed'
        result = self.invoke('compile', self.entry, '--output', output)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((output / 'application.3dsx').exists())
        self.assertTrue((output / 'work/kernel.log').is_file())

    def test_failed_native_tool_stderr_is_retained(self):
        (self.project / 'pubspec.yaml').write_text(
            "name: ctr_invalid_sdk\nenvironment:\n  sdk: '>=99.0.0 <100.0.0'\n")
        output = self.project / 'rejected-package'
        result = self.invoke('compile', self.entry, '--offline', '--output', output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('version solving failed', result.stderr)
        self.assertIn('version solving failed', (output / 'work/packages.log').read_text())
        self.assertFalse((output / 'application.3dsx').exists())

    def test_local_package_resolution_uses_bundled_dart(self):
        (self.project / 'pubspec.yaml').write_text(
            "name: ctr_native_app\nenvironment:\n  sdk: '>=3.11.0 <4.0.0'\n"
            'dependencies:\n  ctr_local_dependency:\n    path: dependency\n')
        dependency = self.project / 'dependency'
        (dependency / 'lib').mkdir(parents=True)
        (dependency / 'pubspec.yaml').write_text(
            "name: ctr_local_dependency\nenvironment:\n  sdk: '>=3.11.0 <4.0.0'\n")
        (dependency / 'lib/value.dart').write_text('const value = 42;\n')
        self.entry.write_text("import 'package:ctr_local_dependency/value.dart';\nvoid main() { print(value); }\n")
        output = self.project / 'package-build'
        result = self.invoke('compile', self.entry, '--project-directory', self.project,
                             '--offline', '--output', output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((output / 'application.3dsx').is_file())
        commands = json.loads((output / 'work/commands.json').read_text())
        packages = [command for command in commands if command['stage'] == 'packages']
        self.assertEqual(len(packages), 1)
        self.assertEqual(Path(packages[0]['executable']), self.sdk / 'host-dart/bin' / ('dart.exe' if os.name == 'nt' else 'dart'))

    def test_existing_output_is_preserved(self):
        output = self.project / 'owned'
        output.mkdir()
        owner = output / 'owner'
        owner.write_text('keep')
        result = self.invoke('compile', self.entry, '--output', output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(output.iterdir()), [owner])
        self.assertEqual(owner.read_text(), 'keep')

    def test_simultaneous_builds_cannot_share_output(self):
        output = self.project / 'shared-output'
        command = [str(self.cli), 'compile', str(self.entry), '--mode', 'jit', '--output', str(output)]
        processes = [subprocess.Popen(command, cwd=self.project, env=dict(os.environ, PATH=''),
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for _ in range(2)]
        outcomes = [(process, process.communicate()) for process in processes]
        self.assertEqual(sum(process.returncode == 0 for process, _ in outcomes), 1, outcomes)
        for process, (_, diagnostic) in outcomes:
            if process.returncode:
                self.assertRegex(diagnostic, 'Output already exists|exclusive directory creation')
        self.assertTrue((output / 'application.3dsx').is_file())


if __name__ == '__main__':
    unittest.main()
