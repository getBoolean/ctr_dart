"""Exercise the native checker against real missing and incompatible compilers."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLCHAIN = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux', 'native Linux entry point')
class NativeLinuxTest(unittest.TestCase):
    def check(self, prefix):
        with tempfile.TemporaryDirectory() as directory:
            profile = json.loads((TOOLCHAIN / 'target-ctr.json').read_text())
            profile['compiler_prefix'] = prefix
            path = Path(directory) / 'profile.json'
            path.write_text(json.dumps(profile))
            return subprocess.run([sys.executable, TOOLCHAIN / 'native_linux.py', 'check',
                                   '--profile', path], text=True, capture_output=True)

    def test_missing_pinned_compiler_is_reported_without_path_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.check(str(Path(directory) / 'absent' / 'arm-none-eabi-'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing pinned compiler', result.stderr)
        self.assertEqual(result.stdout, '')

    @unittest.skipUnless(shutil.which('arm-none-eabi-g++'), 'requires distro ARM compiler')
    def test_incompatible_distro_compiler_is_not_accepted_as_devkitarm(self):
        compiler = shutil.which('arm-none-eabi-g++')
        version = subprocess.check_output([compiler, '-dumpfullversion'], text=True).strip()
        expected = json.loads((TOOLCHAIN / 'versions.json').read_text())['container']['gcc']
        if version == expected:
            self.skipTest('distro compiler matches the pinned GCC version')
        result = self.check(compiler.removesuffix('g++'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('GCC version mismatch', result.stderr)
        self.assertIn(version, result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
