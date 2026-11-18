"""Public command integration tests using local Git repositories only."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=None):
    return subprocess.run([str(x) for x in args], cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class ToolchainTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.upstream = self.base / 'upstream'
        self.upstream.mkdir()
        self.git('init', cwd=self.upstream)
        self.git('config', 'user.name', 'Fixture', cwd=self.upstream)
        self.git('config', 'user.email', 'fixture@example.invalid', cwd=self.upstream)
        self.git('config', 'core.autocrlf', 'false', cwd=self.upstream)
        (self.upstream / 'feature.txt').write_bytes(b'upstream\n')
        self.git('add', 'feature.txt', cwd=self.upstream)
        self.git('commit', '-m', 'fixture', cwd=self.upstream)
        self.rev = self.git('rev-parse', 'HEAD', cwd=self.upstream).stdout.strip()
        (self.upstream / 'feature.txt').write_bytes(b'ctr patch\n')
        patch = self.git('diff', '--binary', cwd=self.upstream).stdout
        self.patch = self.base / 'port.patch'
        self.patch.write_bytes(patch.encode())
        self.git('restore', 'feature.txt', cwd=self.upstream)
        self.profile = self.base / 'profile.json'
        self.profile.write_text(json.dumps({'name': 'ctr-armv6k', 'target_os': 'ctr',
            'target_cpu': 'arm', 'arm_version': 6, 'arm_fpu': 'vfp',
            'arm_float_abi': 'hard', 'arm_use_neon': False,
            'arm_use_integer_division': False, 'thread_pointer': 'soft',
            'cflags': ['-marm', '-march=armv6k', '-mfpu=vfp', '-mfloat-abi=hard', '-mtp=soft']}))
        self.manifest = self.base / 'versions.json'
        self.data = {'schema_version': 1,
            'dart': {'repository': str(self.upstream), 'revision': self.rev, 'version': 'fixture'},
            'patches': [{'path': self.patch.name, 'sha256': hashlib.sha256(self.patch.read_bytes()).hexdigest()}],
            'dependencies': {'depot_tools': {'repository': str(self.upstream), 'revision': self.rev},
                             'dart_deps': {'path': 'DEPS', 'sha256': 'fixture'}},
            'container': {'image': 'fixture@sha256:' + '0' * 64}}
        self.save_manifest()
        self.source = self.base / 'managed'

    def save_manifest(self):
        self.manifest.write_text(json.dumps(self.data))

    def git(self, *args, cwd):
        result = run('git', *args, cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def bootstrap(self):
        return run(sys.executable, ROOT / 'bootstrap.py', '--manifest', self.manifest,
                   '--source', self.source)

    def identity(self, component='host', mode='aot'):
        result = run(sys.executable, ROOT / 'build_sdk.py', 'identity', '--manifest', self.manifest,
                     '--profile', self.profile, '--component', component, '--mode', mode)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_clean_materialization_reproduces_patch_and_is_idempotent(self):
        first = self.bootstrap()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual((self.source / 'feature.txt').read_text(), 'ctr patch\n')
        head = self.git('rev-parse', 'HEAD', cwd=self.source).stdout
        self.assertEqual(self.git('status', '--porcelain', cwd=self.source).stdout, '')
        second = self.bootstrap()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=self.source).stdout, head)
        state = json.loads(first.stdout)
        self.assertEqual(state['upstream_revision'], self.rev)
        self.assertEqual(state['patches'][0]['sha256'], self.data['patches'][0]['sha256'])

    def test_dirty_source_is_refused_and_edits_survive(self):
        self.assertEqual(self.bootstrap().returncode, 0)
        edit = self.source / 'feature.txt'
        edit.write_text('precious edit\n')
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('dirty', result.stderr.lower())
        self.assertEqual(edit.read_text(), 'precious edit\n')

    def test_wrong_clean_source_is_refused_without_reset(self):
        self.assertEqual(self.bootstrap().returncode, 0)
        self.git('checkout', '--detach', self.rev, cwd=self.source)
        head = self.git('rev-parse', 'HEAD', cwd=self.source).stdout
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('mismatch', result.stderr.lower())
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=self.source).stdout, head)

    def test_unmanaged_directory_is_preserved(self):
        self.source.mkdir()
        (self.source / 'keep').write_text('private')
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('unmanaged', result.stderr.lower())
        self.assertEqual((self.source / 'keep').read_text(), 'private')

    def test_patch_hash_mismatch_refuses_before_materializing(self):
        self.patch.write_text('tampered')
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('hash', result.stderr.lower())
        self.assertFalse(self.source.exists())

    def test_icu_patch_is_replayed_and_preserves_local_changes(self):
        sys.path.insert(0, str(ROOT))
        self.addCleanup(lambda: sys.path.remove(str(ROOT)))
        from bootstrap import patch_icu
        from common import verify_icu
        pin = {**self.data['dart'], 'patches': self.data['patches']}
        self.data['dependencies']['icu'] = pin
        self.save_manifest()
        dependency = self.source / 'third_party' / 'icu'
        dependency.parent.mkdir(parents=True)
        self.git('clone', str(self.upstream), str(dependency), cwd=self.base)
        self.git('config', 'core.autocrlf', 'false', cwd=dependency)
        patch_icu(self.source, self.data, self.manifest)
        self.assertEqual((dependency / 'feature.txt').read_text(), 'ctr patch\n')
        head = self.git('rev-parse', 'HEAD', cwd=dependency).stdout
        patch_icu(self.source, self.data, self.manifest)
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=dependency).stdout, head)
        verify_icu(self.source, self.data)
        # gclient can restore the pinned clean dependency on a later sync.
        self.git('checkout', '--detach', self.rev, cwd=dependency)
        patch_icu(self.source, self.data, self.manifest)
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=dependency).stdout, head)
        (dependency / 'feature.txt').write_text('unexpected committed change\n')
        self.git('add', 'feature.txt', cwd=dependency)
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-m', 'unexpected dependency commit', cwd=dependency)
        with self.assertRaisesRegex(RuntimeError, 'mismatch'):
            patch_icu(self.source, self.data, self.manifest)
        self.git('checkout', '--detach', head.strip(), cwd=dependency)
        (dependency / 'feature.txt').write_text('private edit\n')
        with self.assertRaisesRegex(RuntimeError, 'dirty'):
            patch_icu(self.source, self.data, self.manifest)
        self.assertEqual((dependency / 'feature.txt').read_text(), 'private edit\n')
        with self.assertRaisesRegex(RuntimeError, 'dirty'):
            verify_icu(self.source, self.data)

    def test_icu_patch_hash_is_checked_before_source_creation(self):
        self.data['dependencies']['icu'] = {
            **self.data['dart'], 'patches': self.data['patches']}
        self.data['patches'] = []
        self.save_manifest()
        self.patch.write_text('tampered dependency patch')
        result = self.bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('hash', result.stderr.lower())
        self.assertFalse(self.source.exists())

    def test_cache_identity_tracks_all_compatibility_inputs(self):
        initial = self.identity()['cache_key']
        self.assertNotEqual(initial, self.identity(mode='jit')['cache_key'])
        self.assertNotEqual(initial, self.identity(component='target')['cache_key'])
        self.data['dependencies']['depot_tools']['revision'] = '1' * 40
        self.save_manifest()
        self.assertNotEqual(initial, self.identity()['cache_key'])
        self.data['dependencies']['depot_tools']['revision'] = self.rev
        self.save_manifest()
        profile = json.loads(self.profile.read_text())
        profile['cflags'].append('-DNEW_PROFILE=1')
        self.profile.write_text(json.dumps(profile))
        self.assertNotEqual(initial, self.identity()['cache_key'])
        profile['cflags'].pop()
        self.profile.write_text(json.dumps(profile))
        self.patch.write_text(self.patch.read_text() + '\n')
        self.data['patches'][0]['sha256'] = hashlib.sha256(self.patch.read_bytes()).hexdigest()
        self.save_manifest()
        self.assertNotEqual(initial, self.identity()['cache_key'])

    def test_host_and_target_configuration_are_separate(self):
        host = self.identity('host')
        target = self.identity('target')
        self.assertEqual(host['gn_args']['target_os'], 'linux')
        self.assertEqual(host['gn_args']['target_cpu'], 'x64')
        self.assertNotIn('arm_version', host['gn_args'])
        self.assertEqual(target['gn_args']['target_os'], 'ctr')
        self.assertEqual(target['gn_args']['target_cpu'], 'arm')
        self.assertEqual(target['gn_args']['arm_version'], 6)
        self.assertFalse(target['gn_args']['arm_use_neon'])
        self.assertFalse(target['gn_args']['arm_use_integer_division'])
        self.assertEqual(target['gn_args']['arm_float_abi'], 'hard')
        self.assertNotEqual(host['cache_key'], target['cache_key'])

    def test_precompiler_runs_on_linux_and_targets_ctr(self):
        compiler = self.identity('precompiler')
        self.assertEqual(compiler['executable_os'], 'linux')
        self.assertEqual(compiler['executable_cpu'], 'x64')
        self.assertEqual(compiler['gn_args']['target_os'], 'ctr')
        self.assertEqual(compiler['gn_args']['dart_target_arch'], 'arm')
        self.assertEqual(compiler['root_target'], '//build/ctr:precompiler')
        self.assertEqual(self.identity('target', 'aot')['root_target'],
                         '//build/ctr:aot_runtime')
        self.assertEqual(self.identity('target', 'jit')['root_target'],
                         '//build/ctr:jit_runtime')

    def test_specs_content_changes_invalidate_identity(self):
        profile = json.loads(self.profile.read_text())
        profile['link_specs'] = ['ctr.specs']
        self.profile.write_text(json.dumps(profile))
        specs = self.base / 'ctr.specs'
        specs.write_text('first specs')
        initial = self.identity()['cache_key']
        specs.write_text('changed specs')
        self.assertNotEqual(initial, self.identity()['cache_key'])

    def test_identical_inputs_in_another_directory_keep_identity(self):
        profile = json.loads(self.profile.read_text())
        profile['link_specs'] = ['ctr.specs']
        self.profile.write_text(json.dumps(profile))
        specs = self.base / 'ctr.specs'
        specs.write_text('identical relative specs contents')
        other = self.base / 'second-location'
        other.mkdir()
        for path in (self.manifest, self.profile, self.patch, specs):
            shutil.copyfile(path, other / path.name)
        result = run(sys.executable, ROOT / 'build_sdk.py', 'identity',
                     '--manifest', other / self.manifest.name,
                     '--profile', other / self.profile.name, '--component', 'target', '--mode', 'aot')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['cache_key'], self.identity('target')['cache_key'])

    def test_pinned_patch_and_specs_bytes_survive_autocrlf_checkout(self):
        shutil.copyfile(ROOT.parent / '.gitattributes', self.upstream / '.gitattributes')
        manifest = json.loads((ROOT / 'versions.json').read_text())
        all_patches = manifest['patches'] + manifest['dependencies'].get('icu', {}).get('patches', [])
        files = [ROOT / patch['path'] for patch in all_patches] + [ROOT / name for name in
            ('ctr.specs', 'versions.json', 'target-ctr.json', 'common.py', 'build_sdk.py')]
        for path in files:
            destination = self.upstream / 'toolchain' / path.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        self.git('-c', 'core.autocrlf=false', 'add', '.gitattributes', 'toolchain', cwd=self.upstream)
        self.git('commit', '-m', 'locked source inputs', cwd=self.upstream)
        checkout = self.base / 'crlf-checkout'
        self.git('-c', 'core.autocrlf=true', 'clone', '--quiet', self.upstream, checkout, cwd=self.base)
        for patch in all_patches:
            path = checkout / 'toolchain' / patch['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), patch['sha256'])
        self.assertEqual((checkout / 'toolchain' / 'ctr.specs').read_bytes(), (ROOT / 'ctr.specs').read_bytes())
        args = ['identity', '--component', 'target', '--mode', 'aot']
        copied = run(sys.executable, checkout / 'toolchain' / 'build_sdk.py', *args)
        original = run(sys.executable, ROOT / 'build_sdk.py', *args)
        self.assertEqual(copied.returncode, 0, copied.stderr)
        self.assertEqual(original.returncode, 0, original.stderr)
        self.assertEqual(json.loads(copied.stdout)['cache_key'], json.loads(original.stdout)['cache_key'])


@unittest.skipUnless(os.environ.get('CTR_SDK_INTEGRATION') == '1',
                     'set CTR_SDK_INTEGRATION=1 after materializing the pinned SDK')
class SdkPatchReproductionTest(unittest.TestCase):
    def test_actual_sdk_patch_queue_reproduces_the_managed_tree(self):
        actual = Path(os.environ.get('CTR_SDK_SOURCE',
                                     ROOT.parent / 'third_party' / 'dart-sdk'))
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            manifest = json.loads((ROOT / 'versions.json').read_text())
            manifest['dart']['repository'] = str(actual)
            for patch in manifest['patches']:
                patch['path'] = str((ROOT / patch['path']).resolve())
            for patch in manifest['dependencies'].get('icu', {}).get('patches', []):
                patch['path'] = str((ROOT / patch['path']).resolve())
            fixture = base / 'versions.json'
            fixture.write_text(json.dumps(manifest))
            reproduced = base / 'dart-sdk'
            result = run(sys.executable, ROOT / 'bootstrap.py', '--manifest', fixture,
                         '--source', reproduced)
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = run('git', '-C', actual, 'rev-parse', 'HEAD^{tree}')
            observed = run('git', '-C', reproduced, 'rev-parse', 'HEAD^{tree}')
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertEqual(observed.stdout, expected.stdout)
            status = run('git', '-C', reproduced, 'status', '--porcelain')
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(status.stdout, '')


if __name__ == '__main__':
    unittest.main()
