import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('runtime_results', Path(__file__).parents[1] / 'results.py')
results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(results)


class JournalTest(unittest.TestCase):
    def setUp(self):
        self.identity = dict(schema=1, run_id='a' * 32, fixture='hello', mode='jit',
                             compatibility='b' * 64, artifact_sha256='c' * 64,
                             build_id='d' * 64, environment='host')
        self.records = [dict(event='begin', **self.identity),
                        dict(event='output', run_id=self.identity['run_id'], text='async stack\nline'),
                        dict(event='assert', run_id=self.identity['run_id'], name='cleanup', status='pass'),
                        dict(event='terminal', run_id=self.identity['run_id'], outcome='pass', assertions=1)]

    def check(self, records, expected='incomplete', observation=None):
        journal = '\n'.join(results.PREFIX + json.dumps(record) for record in records)
        value = results.validate(journal, self.identity, observation)
        self.assertEqual(value['outcome'], expected, value)

    def test_current_run(self):
        self.check(self.records, 'pass')

    def test_stale_truncated_duplicate_contradictory(self):
        for count in range(len(self.records)):
            self.check(self.records[:count])
        self.check(self.records + [self.records[-1]])
        stale = copy.deepcopy(self.records)
        stale[0]['artifact_sha256'] = '0' * 64
        self.check(stale)
        self.records[2]['status'] = 'fail'
        self.check(self.records)

    def test_timeout_and_crash(self):
        self.check(self.records, 'pass', 'timeout')
        self.check(self.records, observation='crash')

    def test_interleaved_and_malformed(self):
        self.check(self.records[:1] + [dict(event='output', run_id='0' * 32)] + self.records[1:])
        journal = results.PREFIX + json.dumps(self.records[0]) + '\n' + results.PREFIX + '{'
        self.assertEqual(results.validate(journal, self.identity)['outcome'], 'incomplete')
