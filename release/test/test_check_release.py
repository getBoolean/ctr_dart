import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('check_release', Path(__file__).parents[1] / 'check_release.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

VERSION = '9.9.9-test'


class CheckReleaseTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.archive = self.root / f'ctr-dart-{VERSION}-linux-x64.zip'
        self.archive.write_bytes(b'qualified bytes')
        self.entry = dict(sdk_archive=self.archive.name, result='pass',
                          sdk_sha256=hashlib.sha256(b'qualified bytes').hexdigest())

    def tearDown(self):
        self.directory.cleanup()

    def results(self, version=VERSION, **changes):
        path = self.root / f'results-{len(list(self.root.glob("results-*.json")))}.json'
        path.write_text(json.dumps(dict(version=version, hosts=[dict(self.entry, **changes)])))
        return path

    def test_qualified_archive_passes(self):
        self.assertEqual(check.check_release(self.results(), [self.archive], VERSION), [self.archive.name])

    def test_unqualified_archives_are_refused(self):
        other = self.root / f'ctr-dart-{VERSION}-windows-x64.zip'
        other.write_bytes(b'qualified bytes')
        stale = self.root / 'ctr-dart-0.0.1-linux-x64.zip'
        stale.write_bytes(b'qualified bytes')
        cases = [
            ('results for another version', self.results(version='0.0.1'), self.archive, 'not ' + VERSION),
            ('changed bytes', self.results(sdk_sha256='0' * 64), self.archive, 'differs'),
            ('failed qualification', self.results(result='fail'), self.archive, 'did not pass'),
            ('missing host record', self.results(), other, 'no qualification record'),
            ('older version name', self.results(sdk_archive=stale.name), stale, 'no qualification record'),
        ]
        for label, results, archive, message in cases:
            with self.subTest(label), self.assertRaisesRegex(ValueError, message):
                check.check_release(results, [archive], VERSION)

    def test_default_version_comes_from_the_preview_manifest(self):
        current = json.loads((check.ROOT / 'release/preview.json').read_text(encoding='utf-8'))['version']
        self.assertNotEqual(current, VERSION)
        with self.assertRaisesRegex(ValueError, 'not ' + current):
            check.check_release(self.results(), [self.archive])
