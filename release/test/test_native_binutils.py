"""Pure producer-policy tests; these do not qualify a native toolchain."""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location(
    "native_binutils", Path(__file__).parents[1] / "native_binutils.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


class ProducerPolicyTest(unittest.TestCase):
    def test_windows_rejects_msys_and_unbundled_runtime(self):
        native.check_dependencies("windows-x64", ["KERNEL32.dll", "msvcrt.dll"])
        for dependency in ("msys-2.0.dll", "libwinpthread-1.dll", "libgcc_s_seh-1.dll"):
            with self.subTest(dependency=dependency), self.assertRaises(ValueError):
                native.check_dependencies("windows-x64", [dependency])

    def test_mac_rejects_homebrew_and_relative_dependencies(self):
        native.check_dependencies("macos-arm64", ["/usr/lib/libSystem.B.dylib"])
        for dependency in ("/opt/homebrew/lib/libz.dylib", "@rpath/libintl.dylib"):
            with self.subTest(dependency=dependency), self.assertRaises(ValueError):
                native.check_dependencies("macos-arm64", [dependency])

    def test_linux_rejects_non_system_dependencies_and_newer_glibc(self):
        native.check_dependencies("linux-x64", ["libc.so.6", "libm.so.6"], ["2.2.5", "2.36"])
        with self.assertRaises(ValueError):
            native.check_dependencies("linux-x64", ["libz.so.1"], ["2.36"])
        with self.assertRaises(ValueError):
            native.check_dependencies("linux-x64", ["libc.so.6"], ["2.37"])

    def test_source_digest_mismatch_is_fatal(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "source.tar.xz"
            archive.write_bytes(b"wrong source")
            with self.assertRaisesRegex(ValueError, "source digest mismatch"):
                native.verify_source(archive, {"sha256": "0" * 64, "sha512": "0" * 128})

    def test_archive_cannot_escape_source_root(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "source.tar.xz"
            with tarfile.open(archive, "w:xz") as stream:
                member = tarfile.TarInfo("binutils-2.46.0/../../escape")
                member.size = 1
                stream.addfile(member, io.BytesIO(b"x"))
            with self.assertRaises(ValueError):
                native.extract_source(archive, Path(directory) / "unpacked", "binutils-2.46.0")
            self.assertFalse((Path(directory) / "escape").exists())


if __name__ == "__main__":
    unittest.main()
