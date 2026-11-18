# Complete native SDK preview

The requested distribution is a compiled CLI with every tool and target asset
needed for supported AOT/JIT builds. It must run without installing Python,
PowerShell, Docker, make or a separate cross compiler. Producer-side CI may use
build scripts; those scripts are not the delivered build pipeline.

An earlier Docker-based frontend was not this deliverable, was never released
and has been removed. The first source preview is historical, not a complete
native SDK.

## Established evidence

- The SDK remains the 32-patch tree at
  `7eb1156c65309c5c531b82f409ae242c06a33b29`.
- The compiled Linux SDK built hello, async, GC stress, exceptions and focused
  numerics in both AOT and JIT modes. Networking was disabled, the SDK mount was
  read-only, no source SDK checkout was mounted and PATH contained only bundled
  tools. These ten build receipts are separate from target execution evidence.
- A host-only GN graph generated successfully without SDK source edits, using
  native `current_os`/`current_cpu` with CTR target OS and explicit ARMv6K Dart
  target architecture. Its definitions contain `TARGET_ARCH_ARM`,
  `DART_TARGET_OS_CTR` and `DART_TARGET_ARMV6K`. Windows, Intel Mac and Apple
  Silicon precompiler CI builds have passed. The final producers record their
  native-only sort and target-alignment inputs separately from the SDK32 base;
  the target runtime and patch queue remain unchanged.
- Exported target assets occupy 52,966,338 bytes after removing debug sections.
  Original archives remain unchanged. Both modes passed actual native-offset
  checks: 483 AOT and 486 JIT constants, with zero mismatches. Target C++ assertions
  establish the 32-byte Program structure and its eight 32-bit fields.
- The independent Dart ELF-to-3DSX encoder matches the reference converter byte
  for byte on all ten newly linked ELF inputs.
- Real native CLI checks passed for both modes in paths with spaces, invalid
  source without publication, preserving existing outputs and resolving a local
  package dependency offline using the bundled Dart resolver.
- A fresh hello AOT built and staged by the native CLI ran in Azahar 2126.2,
  printed `hello:42`, passed cleanup and emitted a matching terminal record.
  The initial staging attempt exposed a configuration-field ordering defect,
  which was corrected before this pass. No JIT emulator or new
  physical-console execution pass is claimed here.
- Independent GNU assembler/linker CI builds passed for all four native hosts.
  The complete Linux bundle passed native dependency inspection; its tools use
  standard glibc components only. The release baseline is glibc 2.36 or newer.

The generated precompiler snapshot hash is
`c5e274828bf37a90359bd3b0753e3eb2`, with SDK short hash `7eb1156c65`.
No stock hash is substituted. Producer graph changes must preserve these
identities and still require generated-code/runtime compatibility checks.

## Delivery components

Each native host bundle needs the compiled CLI, CTR kernel compiler, CTR
`gen_snapshot`, GNU ARM assembler/linker, a native dependency resolver, and
prebuilt platform/runtime/launcher/startup/math/library assets. The converter
is implemented in the compiled Dart CLI. Build arguments use explicit bundled
paths; recipient machines must not supply an interpreter or compiler.

Native host tools are built separately for Windows x64, Linux x64, macOS Intel
and Apple Silicon. Runtime assets can be shared across hosts, with per-mode
compatibility identities retained. A host executable smoke test is distinct
from an offline source-to-3DSX build and from actual target execution.

## Distribution and qualification

The first four-host packaging run was stopped before execution by account
billing limits. The next run executed all four jobs. Linux completed its
extracted-archive checks; Windows and both macOS hosts failed the reference
assembly comparison. Investigation led to the native-only sort and target
alignment fixes, and the remaining cross-host difference was narrowly verified
as the DWARF producer host name.

All four extracted native SDKs pass six real integration checks, including
retaining failed native-tool stderr and rejecting two builds that compete for
one output directory. Exclusive output reservation uses the host OS's atomic
directory creation. Its Linux ownership tests also reject a deliberate
nonexclusive-creation mutation. Windows path-preservation expectations were
corrected to use native separators without weakening the ownership assertions.

The complete SDK check passed for each host: Windows x64, Linux x64,
macOS Intel and macOS Apple Silicon.

Independent inspection of each downloaded SDK verified every sealed file,
manifest and archive digest, GNU corresponding-source digest and Unix
executable mode. A fresh AOT sample produced by each host also ran in Azahar
2126.2, printed `native:42` and passed cleanup and terminal validation.
The release receipts bound each SDK, CI run, target artifact and accepted run
identity. New JIT emulator or physical-console execution is not claimed.

Do not redistribute the branded devkitARM host-tool distribution. Native GNU
assembler/linker producers use independently pinned upstream sources and retain
GNU notices, exact corresponding source and build material. Target library
notices, source availability and the MPL startup/linker layout are included.
The upstream converter's conflicting license metadata is
not used as permission to redistribute it.

The converter's format encoding was checked against the layout documented by
the [Azahar loader](https://github.com/azahar-emu/azahar/blob/master/src/core/loader/3dsx.cpp)
and existing ELF/3DSX pairs. No converter source was copied into the Dart encoder.

Native producer CI, dependency closure, archive integrity, cross-host probe
code generation and supported AOT/JIT builds from extracted downloads passed.
The converter comparisons and per-host AOT emulator samples are additional
evidence. Existing ten hardware passes retain their original artifact
identities. Universal Dart APIs, FFI/native packages and Flutter remain
unfinished milestones.
