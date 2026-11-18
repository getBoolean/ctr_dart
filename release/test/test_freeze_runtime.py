from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freeze_runtime import freeze_runtime


class RuntimeExportTest(unittest.TestCase):
    def test_existing_directory_is_preserved_before_source_access(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            owner = output / 'owner'
            owner.write_text('keep')
            with self.assertRaisesRegex(RuntimeError, 'exists'):
                freeze_runtime(output / 'absent-sdk', output / 'absent-build', output)
            self.assertEqual(list(output.iterdir()), [owner])
            self.assertEqual(owner.read_text(), 'keep')
