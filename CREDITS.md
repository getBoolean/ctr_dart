# Credits and provenance

This record identifies software used or referenced by the experimental Dart CTR
port. Inclusion is attribution and provenance, not endorsement. Exact source,
toolchain, patch and dependency pins are in `toolchain/versions.json`.

## Software and tools used

- **Dart SDK, the Dart project authors:** compiler, VM, core libraries and test
  sources used as the port's upstream foundation. The CTR changes are preserved
  as an ordered patch queue. [Dart SDK](https://github.com/dart-lang/sdk),
  [bundled license](release/licenses/dart.LICENSE).
- **ICU and Unicode contributors:** the pinned Dart build's Unicode dependency,
  with a recorded newlib portability patch. [ICU](https://github.com/unicode-org/icu),
  [bundled notice](release/licenses/icu.LICENSE).
- **devkitPro contributors:** the official pinned devkitARM image, libctru and
  3DS tools supply the cross compiler, hardware/runtime interfaces and ELF-to-3DSX
  conversion. [devkitPro](https://devkitpro.org/),
  [libctru](https://github.com/devkitPro/libctru).
- **GCC and newlib contributors:** GCC runtime software arithmetic and newlib
  software math are linked through the selected official multilib providers.
  Provider hashes and actual linked imports/exports are recorded by the build.
  GCC runtime licensing includes the GCC Runtime Library Exception; retain the
  licenses/notices applicable to the exact toolchain and linked libraries.
  [GCC runtime exception](https://www.gnu.org/licenses/gcc-exception-3.1.html),
  [newlib licensing](https://sourceware.org/newlib/COPYING.NEWLIB).
- **GNU Binutils contributors:** independent native ARM assembler and linker
  builds from unmodified upstream source are used in the complete SDK pipeline.
  Exact source checksums, build material and dependency audits accompany the
  producer outputs. [GNU Binutils](https://sourceware.org/binutils/).
- **Chromium/depot_tools, GN, Ninja and LLVM/Clang contributors:** pinned host
  dependency synchronization, build generation and host compiler tools used by
  the SDK build. Their own source/distribution notices remain applicable.
- **Dart `args`, `path`, `crypto`, `ffi` and `test` contributors:** argument parsing, host path
  handling and CLI tests; versions are locked in `packages/ctr_dart/pubspec.lock`.
  The standalone host executable includes `args`, `path`, `crypto` and `ffi`; their
  notices are bundled under `release/licenses/`.
  `test` is a development dependency.
  Host-side FFI reserves output directories atomically through the operating
  system; this does not expose FFI to 3DS applications.
- **Azahar contributors:** actual AOT emulator execution used in qualification.
  [Azahar](https://github.com/azahar-emu/azahar). Emulator success is not substituted
  for physical-console evidence.
  Its loader was also inspected for 3DSX format facts while implementing the
  CLI's independent ELF-to-3DSX encoder; no converter source was copied.
- **LumaTeam and Homebrew Launcher contributors:** the owner's modified-console
  launch environment for the reported physical New 3DS tests. Exact installed
  environment versions remain unrecorded.
- **LumaTeam, BootNTR/NTR and Chokistream contributors:** network input redirection
  and decoded screen capture used to establish agent-assisted console control.
  These tools are not bundled with the Dart preview.

## Reference material and related projects

ARM architecture documentation, 3dbrew and upstream source inspection informed
the compiler, ABI and platform work.
The separate [emucap project](https://github.com/getBoolean/emucap) owns emulator
bridge integration; its planned capabilities are not claimed as shipped here.
The project is independent of Nintendo and is not an official Nintendo SDK.

## AI assistance and accountability

OpenAI Codex and Anthropic Claude have assisted research, source implementation,
debugging, tests and documentation through the development workflow. Generated
output is not accepted solely because an AI produced it: claims require source
provenance and reproducible checks, and hypotheses remain distinct from measured
results. Maintainers remain responsible for review, licensing, testing and
release decisions. The preserved curated passes establish only their documented
scope, not arbitrary Dart or Flutter compatibility.
