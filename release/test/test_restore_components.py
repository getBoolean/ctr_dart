import importlib.util
import hashlib
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))

spec = importlib.util.spec_from_file_location('restore_components', Path(__file__).parents[1] / 'restore_components.py')
restore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)


class TransportRecoveryTest(unittest.TestCase):
    def test_original_recipe_line_endings_match_both_producer_inventories(self):
        expected = {
            'native-binutils-workflow.yml': 'cb52befceadec595da45a7fda9d516bf621f2c74c6372cafe927aaedda384289',
            'native-binutils-workflow-windows.yml': '35d63754e009f660ef1f1e560ed78fb3732cefd64c37cea816d4fd95f9c0aa3c',
        }
        for name, sha in expected.items():
            self.assertEqual(hashlib.sha256((restore.DATA / name).read_bytes()).hexdigest(), sha)

    def test_exact_missing_bytes_are_restored_without_overwriting_existing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            donor = root / 'donor'
            donor.write_bytes(b'original upstream metadata\n')
            expected = hashlib.sha256(donor.read_bytes()).hexdigest()
            destination = root / 'component/.metadata'
            restore.restore_file(destination, donor, expected)
            self.assertEqual(destination.read_bytes(), donor.read_bytes())
            destination.write_bytes(b'owner')
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                restore.restore_file(destination, donor, expected)
            self.assertEqual(destination.read_bytes(), b'owner')

    def test_unmatched_donor_cannot_create_a_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            donor = root / 'donor'
            donor.write_bytes(b'different SDK')
            destination = root / 'component/.metadata'
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                restore.restore_file(destination, donor, '0' * 64)
            self.assertFalse(destination.exists())
