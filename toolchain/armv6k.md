# ARMv6K compiler source checks

The third SDK patch restores an ARM-state ARMv6K/VFPv2 register and instruction
profile. `dart_armv6k` defaults to true for the CTR target in both host-precompiler
and device-runtime graphs. CTR cannot disable it. Linux simarm can select the same
profile explicitly for compiler tests; this does not identify Linux as CTR.

The profile has D0-D15, a hard-float calling convention, no NEON, and no hardware
integer division. Runtime feature flags cannot enable unsupported target features.
Patchable constants use four conditional MOV/ORR instructions. Their decoder,
patcher, far-branch fixups and PC-relative trampoline sizes account for that width.
ARMv7 retains its MOVW/MOVT sequences. Bitfield extraction, multiply-subtract and
bit reversal have ARMv6K replacements; generated barriers use the ARM11 CP15 form.

The simulator rejects MOVW/MOVT, ARMv7 barriers, NEON, hardware division,
bitfield-extract/RBIT/MLS encodings, VFP immediate loads, newer VFP conversion
forms, and double registers beyond D15. Its ordinary decoder still rejects
unknown instructions. Literal-encoding tests and expected-crash execution tests
exercise the restriction independently of the assembler.

## Reproduce the compiler tests

Bootstrap the pinned source and dependencies with `bootstrap.py --sync-deps` in
the pinned Linux container. Install a 32-bit Linux runtime when using simarm on
an x64 host (`libc6-i386` and `lib32stdc++6` on Debian). From the managed SDK:

```sh
python3 tools/gn.py --arch=simarm --mode=release
buildtools/ninja/ninja -C out/ReleaseSIMARM -j6 run_vm_tests
out/ReleaseSIMARM/run_vm_tests --list
out/ReleaseSIMARM/run_vm_tests Armv6KImmediatePattern
out/ReleaseSIMARM/run_vm_tests Armv6KInstructionLegality
out/ReleaseSIMARM/run_vm_tests ArmTrampolineRelocation
out/ReleaseSIMARM/run_vm_tests Assembler_PatchableConstantRoundTrip
out/ReleaseSIMARM/run_vm_tests Assembler_ArmProfileReplacements
out/ReleaseSIMARM/run_vm_tests Assembler_NearBranchRelocation
out/ReleaseSIMARM/run_vm_tests Assembler_FarBranchRelocation
```

Repeat with `--gn-args='dart_armv6k=true'` passed to `tools/gn.py`, then rebuild.
That profile additionally registers `Armv6KRejectMovw`, `Armv6KRejectDmb`,
`Armv6KRejectVfpImmediate`, and `Armv6KRejectD16` as expected crashes. Each must
terminate with the simulator's unimplemented-instruction diagnostic; an exit of
zero is a failure. Provide closed stdin when running those cases directly.

Existing integer-division, double arithmetic/conversion, call-preservation, and
code-relocator tests cover the affected consumers. Compiler tests that load Dart
source use `--dfe=out/ReleaseSIMARM/gen/kernel_service.dill`, generated from the
same SDK. These include write-barrier elimination, catch-entry moves,
deoptimization regressions, unhandled exceptions and Dart safepoint stress.

## Source verification recorded on 2026-11-04

- ARMv7 simarm: 42 focused cases and six compiler/stress cases passed.
- Restrictive ARMv6K simarm: the same 48 cases passed. Four literal instruction
  execution cases terminated with the expected rejection diagnostic.
- ARMv6K unhandled-exception execution additionally passed with optimization
  disabled and with synchronous optimization after ten calls.
- The toolchain suite passed all 12 tests with real SDK patch reproduction
  enabled, including source preservation and LF/hash checks.
- Fresh bootstrap of the final queue produced SDK tree
  `2bc69b542162d8194c51cd9201c766301c98a96f`, matching the worker's source tree.
  The first two patches are unchanged; the manifest records the third patch hash.
- The real CTR host-precompiler GN graph compiled the assembler, instruction
  patterns, ARM lowering, flow-graph compiler and stubs. Its commands contain both
  `DART_TARGET_OS_CTR` and `DART_TARGET_ARMV6K`. Native AOT/JIT GN generation passed.
  Complete generator/runtime links were not qualified.

The initial decoder characterization aborted on a legal MOV/ORR constant load.
Negative ISA tests failed to compile before the restriction existed. Subsequent
execution caught an incorrectly encoded rotated mask in the bit-reversal
replacement; correcting it made both the existing RBIT test and the combined
replacement test pass. These failures were observed before claiming a pass.

Audit coverage includes the assembler's immediate and VFP emitters, integer
lowering, class-id extraction, division/modulo consumers, register-bank and spill
limits, allocation/write-barrier stubs, safepoint barriers, call patterns,
exception/deoptimization tests and the AOT relocator's trampoline-size consumer.
NEON population-count lowering already checks target support and remains gated
by that existing capability check. No numeric software helpers were added.

## Evidence boundaries

These are compiler source-delivery checks. The simulator performs C++ arithmetic
on the host and does not model ARM11 floating-point exception assistance, FPSCR
flush-to-zero/default-NaN behavior, cache publication or libctru scheduling.
VFPv2 legality does not qualify Dart numeric semantics. Software-assisted
arithmetic, comparisons, conversions and parse/format auditing remain necessary.

The native CTR OS, cache/memory contracts, complete precompiler/runtime links,
packaging, and optimized/unoptimized curated execution on hardware and Azahar
remain separate integration and qualification gates. No target execution is
claimed by these checks.
