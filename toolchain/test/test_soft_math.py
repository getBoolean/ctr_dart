import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import DEFAULT_PROFILE
from soft_math import prepare, validate_component
from libm_reference import agrees


class SoftMathInputTest(unittest.TestCase):
    def test_numeric_allowance_preserves_special_values_and_rounding(self):
        self.assertFalse(agrees(0, 0, 1))
        self.assertFalse(agrees(0, 1, 0))
        self.assertFalse(agrees(0, 1 << 63, 0))
        self.assertFalse(agrees(10, 0x3ff0000000000001, 0x3ff0000000000000))
        self.assertTrue(agrees(1, 0x3ff0000000000002, 0x3ff0000000000000))
        self.assertFalse(agrees(1, 0x3ff0000000000003, 0x3ff0000000000000))

    def test_wrong_provider_is_refused_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = root / 'wrong.a'
            provider.write_bytes(b'not the pinned provider')
            output = root / 'component'
            with self.assertRaisesRegex(RuntimeError, 'provider hash'):
                prepare(output, json.loads(DEFAULT_PROFILE.read_text()), provider)
            self.assertFalse(output.exists())

    def test_soft_float_public_profile_is_refused(self):
        profile = json.loads(DEFAULT_PROFILE.read_text())
        profile['arm_float_abi'] = 'soft'
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'hard-float'):
                prepare(Path(directory) / 'component', profile, Path('absent.a'))


@unittest.skipUnless(os.environ.get('CTR_SOFT_MATH_INTEGRATION') == '1',
                     'set CTR_SOFT_MATH_INTEGRATION=1 for real provider compilation')
class SoftMathNativeTest(unittest.TestCase):
    def test_real_component_and_unexpected_export_rejection(self):
        profile = json.loads(DEFAULT_PROFILE.read_text())
        prefix = profile['compiler_prefix']
        provider = Path(subprocess.check_output([
            prefix + 'g++', '-marm', '-march=armv6k', '-mfloat-abi=soft',
            '-print-file-name=libm.a'], text=True).strip())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            component, record = prepare(root / 'component', profile, provider)
            self.assertEqual(len(record['exports']), 14)
            self.assertEqual(validate_component(component, profile), record['audit'])
            source = root / 'unexpected.cc'
            source.write_text('extern "C" double UnexpectedExport(double x) { return x; }\n')
            obj = root / 'unexpected.o'
            subprocess.run([prefix + 'g++', *profile['cflags'], '-c', source, '-o', obj], check=True)
            changed = root / 'changed.o'
            subprocess.run([prefix + 'ld', '-r', component, obj, '-o', changed], check=True)
            with self.assertRaisesRegex(RuntimeError, 'exports'):
                validate_component(changed, profile)
            imported = root / 'unexpected-import.o'
            subprocess.run([prefix + 'objcopy', '--redefine-sym', '__errno=UnexpectedErrno',
                            component, imported], check=True)
            with self.assertRaisesRegex(RuntimeError, 'unexpected software math imports'):
                validate_component(imported, profile)


if __name__ == '__main__':
    unittest.main()
