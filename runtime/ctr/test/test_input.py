"""Host service-injection checks; not CTR initialization qualification."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class InputTest(unittest.TestCase):
    def test_input_failure_never_polls_and_owned_references_are_balanced(self):
        test = Path(__file__).parent
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'input-test'
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I' + str(test / 'input_host'),
                            '-I' + str(test.parent / 'source'),
                            str(test / 'input_test.cc'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
