"""Keep the cross-host code comparison strict outside DWARF producer identity."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
spec = importlib.util.spec_from_file_location('build_native_sdk', Path(__file__).parents[1] / 'build_native_sdk.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class CodeGenerationContract(unittest.TestCase):
    version = 'Dart SDK version: 3.14.0 on "macos_arm"'
    banner = '.string ' + json.dumps('Dart 3.14.0 on "linux_arm"\n') + '\n'
    reference = ('.text\n.long 0xe1a00000\n.section .rodata\n.long 42\n'
                 '.section .debug_info,""\n' + banner).encode()
    expected = hashlib.sha256(reference).hexdigest()
    mac = reference.replace(b'linux_arm', b'macos_arm')

    def test_only_the_exact_dwarf_producer_host_may_differ(self):
        result = build.verify_codegen(self.mac, self.expected, 'macos-arm64', self.version)
        self.assertEqual(result['match'], 'dwarf-producer-host-only')
        self.assertEqual(result['comparable_sha256'], self.expected)
        self.assertEqual(result['sha256'], hashlib.sha256(self.mac).hexdigest())
        result = build.verify_codegen(self.reference, self.expected, 'linux-x64', '')
        self.assertEqual(result['match'], 'exact')

    def test_instruction_data_version_and_non_dwarf_changes_are_rejected(self):
        for changed in [self.mac.replace(b'0xe1a00000', b'0xef000000'),
                        self.mac.replace(b'.long 42', b'.long 43'),
                        self.mac.replace(b'3.14.0', b'3.14.1'),
                        self.mac.replace(b'.debug_info', b'.rodata'),
                        self.mac + self.banner.encode()]:
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    build.verify_codegen(changed, self.expected, 'macos-arm64', self.version)

    def test_wrong_compiler_architecture_and_host_are_rejected(self):
        for host, version in [('macos-arm64', self.version.replace('_arm', '_arm64')),
                              ('windows-x64', self.version)]:
            with self.assertRaises(ValueError):
                build.verify_codegen(self.mac, self.expected, host, version)
