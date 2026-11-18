"""Native comparator-pointer contract for the producer's stable qsort."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which('cc'), 'native C compiler required')
class NativeSortContract(unittest.TestCase):
    def test_comparator_arguments_remain_in_the_original_array(self):
        with tempfile.TemporaryDirectory() as directory:
            library = Path(directory) / 'sort.so'
            source = Path(__file__).parents[1] / 'native_stable_sort.c'
            subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Dqsort=ctr_test_sort',
                            str(source), '-o', str(library)], check=True)
            values = (ctypes.c_int * 33)(*reversed(range(33)))
            first = ctypes.addressof(values)
            end = first + ctypes.sizeof(values)
            violations = []
            callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
            def compare(left, right):
                if not (first <= left < end and first <= right < end):
                    violations.append((left, right))
                a = ctypes.cast(left, ctypes.POINTER(ctypes.c_int)).contents.value
                b = ctypes.cast(right, ctypes.POINTER(ctypes.c_int)).contents.value
                return (a > b) - (a < b)
            callback = callback_type(compare)
            sort = ctypes.CDLL(str(library)).ctr_test_sort
            sort.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, callback_type]
            sort(values, len(values), ctypes.sizeof(ctypes.c_int), callback)
            self.assertFalse(violations, 'qsort compared temporary-buffer addresses')
            self.assertEqual(list(values), list(range(33)))
