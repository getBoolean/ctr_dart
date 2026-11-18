"""Packaging contracts; opt-in integration uses the real SDK, compiler and payloads."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from package_runtime import package


class PackagingRejectionTest(unittest.TestCase):
    def test_invalid_fixture_never_reaches_the_toolchain(self):
        with self.assertRaisesRegex(ValueError, 'fixture token'):
            package('/missing', '/missing', 'aot', '/missing', 'bad"fixture', '/missing')

    def test_existing_output_is_preserved_before_any_work(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            marker = output / 'user-data'
            marker.write_bytes(b'keep')
            with self.assertRaisesRegex(RuntimeError, 'already exists'):
                package('/missing', '/missing', 'aot', '/missing', 'hello', output)
            self.assertEqual(marker.read_bytes(), b'keep')
            self.assertEqual(list(output.iterdir()), [marker])


@unittest.skipUnless(os.environ.get('CTR_PACKAGE_INTEGRATION') == '1',
                     'set CTR_PACKAGE_INTEGRATION=1 with real SDK/build/payload paths')
class NativePackagingIntegrationTest(unittest.TestCase):
    def test_real_packages_and_failures_in_paths_with_spaces(self):
        source = Path(os.environ['CTR_PACKAGE_SDK'])
        root = Path(os.environ['CTR_PACKAGE_OUTPUT_ROOT'])
        root.mkdir(parents=True, exist_ok=False)
        records = {}
        for mode in ('aot', 'jit'):
            build = Path(os.environ['CTR_PACKAGE_' + mode.upper() + '_BUILD'])
            payload = Path(os.environ['CTR_PACKAGE_' + mode.upper() + '_PAYLOAD'])
            output = root / (mode + ' with spaces')
            if mode == 'aot':
                records[mode] = package(source, build, mode, payload, 'numeric', output)
            else:
                result = subprocess.run([
                    sys.executable, str(Path(__file__).parents[1] / 'package_runtime.py'),
                    '--source', str(source), '--runtime-build', str(build), '--mode', mode,
                    '--payload', str(payload), '--fixture', 'hello', '--output', str(output)],
                    check=True, text=True, stdout=subprocess.PIPE)
                records[mode] = json.loads(result.stdout)
            published = output / 'package'
            artifact = published / 'application.3dsx'
            record = json.loads((published / 'artifact.json').read_text())
            self.assertEqual(record, records[mode])
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), record['artifact_sha256'])
            self.assertEqual(record['mode'], mode)
            self.assertEqual(record['payload_sha256'], hashlib.sha256(payload.read_bytes()).hexdigest())
            component = output / 'work/soft-math/component.o'
            self.assertEqual(record['software_math']['object_sha256'],
                             hashlib.sha256(component.read_bytes()).hexdigest())
            commands = json.loads((output / 'work/commands.json').read_text())
            links = [row['argv'] for row in commands if '-o' in row['argv'] and
                     row['argv'][row['argv'].index('-o') + 1].endswith('application.elf')]
            self.assertEqual(len(links), 1)
            self.assertFalse(any('no-warn-mismatch' in arg for arg in links[0]))
        self.assertNotEqual(records['aot']['compatibility'], records['jit']['compatibility'])
        self.assertNotEqual(records['aot']['build_id'], records['jit']['build_id'])
        wrong = root / 'wrong mode'
        with self.assertRaisesRegex(RuntimeError, 'identity differs'):
            package(source, Path(os.environ['CTR_PACKAGE_AOT_BUILD']), 'jit',
                    Path(os.environ['CTR_PACKAGE_JIT_PAYLOAD']), 'hello', wrong)
        self.assertFalse(wrong.exists())
        bad = root / 'invalid assembly.S'
        bad.write_text('deliberately invalid assembler input\n')
        output = root / 'failed compilation'
        with self.assertRaises(subprocess.CalledProcessError):
            package(source, Path(os.environ['CTR_PACKAGE_AOT_BUILD']), 'aot', bad, 'hello', output)
        self.assertFalse((output / 'package').exists())
        self.assertTrue((output / 'work/commands.json').is_file())


if __name__ == '__main__':
    unittest.main()
