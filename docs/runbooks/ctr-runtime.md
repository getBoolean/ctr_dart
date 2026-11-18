# Building and qualifying CTR runtime primitives

The repository provides a locked SDK source/patch queue, distinct host and CTR
GN configurations and an experimental Dart embedder. Five curated programs now
execute and clean up on physical New 3DS in both AOT and JIT modes. See the
[supported-feature inventory](../ctr-supported-features.md). Earlier Azahar
runs are separate emulator evidence. The ten hardware passes establish this
bounded runtime milestone; wider Dart compatibility and other Nintendo targets
remain open.

## Locked SDK and host tools

Use [the named Compose service](../ctr-compose.md) with host-folder bind mounts
for all Linux builds and tests. The commands below run inside its `toolchain`
service, container `ctr-dart-toolchain`.

`toolchain/versions.json` pins the published Dart beta, upstream revision, ordered
patch hashes, DEPS digest, depot_tools, GN, Clang, Ninja, and devkitPro versions.
Local builds execute the pinned image. CI migration is separate work.
`target-ctr.json` owns the ARMv6K/VFPv2 hard-float profile and composed linker specs.
The specs select CP15 barriers once and retain their implementation; merely
stacking the two upstream specs causes a rename conflict, and an unrooted alias
can resolve to zero.

Keep SDK/dependency/build caches in the case-sensitive Linux host folder bound
at `/state`. From PowerShell in the repository, set `CTR_IMAGE` from
`toolchain/versions.json` and `CTR_STATE_DIR` to the existing host folder as
documented in the Compose guide. Run the following commands through
`docker compose exec -T toolchain`; paths are container paths:

```sh
python3 toolchain/native_linux.py check
# Prevent inherited Windows-style Git conversion in dependency checkouts.
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.autocrlf GIT_CONFIG_VALUE_0=false
python3 toolchain/bootstrap.py --source /state/sdk --depot-tools /state/depot_tools --sync-deps
python3 toolchain/build_sdk.py build --source /state/sdk --component probe --mode jit
python3 toolchain/build_sdk.py configure --source /state/sdk --component host --mode jit
python3 toolchain/build_sdk.py configure --source /state/sdk --component precompiler --mode aot
python3 toolchain/build_sdk.py configure --source /state/sdk --component target --mode aot
python3 toolchain/build_sdk.py configure --source /state/sdk --component target --mode jit
```

Bootstrap refuses to overwrite unmanaged, dirty or mismatched sources. Export
changes as tracked patches and update their hashes, then use a new source
directory for a changed queue. All managed patches must remain reproducible.

`identity` prints the compatible inputs/cache key without building. Configure and
build verify the checkout and GN hash. Components distinguish Linux executables
from ARM libraries; modes select separate runtime graphs. Both native runtime
archives, the host precompiler and complete AOT/JIT launchers now build and link.
Successful GN generation alone is not a VM build or execution receipt.
`--check-includes` exposes upstream include ownership checking; that audit
currently reports errors on both the patched and exact upstream graphs. Not all
errors have been classified. The isolated native GN probe passes strict checking.

## Runtime assets for the native SDK

The complete SDK workflow (`.github/workflows/native-sdk.yml`) consumes a
`ctr-runtime-assets.zip` and, for Linux, a `ctr-native-precompiler-linux-x64.zip`
from a release, each pinned by SHA-256. After building both `target` runtime
graphs with `build_sdk.py build`, a producer exports and archives the target
assets in the Compose service:

```sh
python3 release/freeze_runtime.py --source /state/sdk --build-root /state/sdk/out/ctr --output <new-runtime-dir>
python3 release/archive_runtime.py --runtime <new-runtime-dir> --output <new-dir>/ctr-runtime-assets.zip --probe-kernel <kernel.dill> --precompiler <reference-gen_snapshot>
```

`freeze_runtime.py` checks the pinned toolchain, compiles the launcher sources in
`runtime/ctr/source` for both modes, checks native offsets and the platform's
private hooks, and records every exported file in `runtime.json`.
`archive_runtime.py` adds the bundled notices and records the reference AOT
assembly that `release/build_native_sdk.py` compares against each host's
precompiler. The Linux compiler component is the output folder of
`release/native_precompiler.py` run on Linux x64.

## Runtime results

The launcher writes `CTR_RUNTIME` JSON records to `ctr-runtime.log` on the SD
card. `runtime/ctr/results.py` validates one journal against the identity in
the matching `run.json`: schema, run ID, fixture, mode, compatibility,
artifact hash, build ID and environment. Records from other runs are ignored;
interleaved runs, records before `begin` or after the terminal record, and
contradictory cleanup/terminal outcomes are rejected.

Outcomes are `pass`, `fail` or `incomplete`. A journal without a begin, cleanup
assertion or terminal record is incomplete. A host-observed crash never
qualifies as a pass. Prepare a fresh run for every launch.

## Host checks

```sh
python3 -m unittest discover -s toolchain/test -v
python3 -m unittest discover -s runtime/ctr/test -v
python3 -m unittest discover -s release/test -v
```

The runtime suite validates journal parsing and compiles the launcher's input
host check. Set `CTR_SDK_INTEGRATION=1` for the toolchain suite to reproduce
the complete managed SDK tree in a temporary directory after materialization.
Run these suites through `docker compose exec -T toolchain`.
CI runs these host checks and the CLI package's analysis and tests. It does not
run the guest.

## Build a Dart entrypoint

Applications are built with the `ctr` CLI from `packages/ctr_dart`, shipped in
the complete native SDK; see the [release usage instructions](../../release/README.md).
Run its checks with the pinned Dart from the Compose service, keeping
`PUB_CACHE` on `/state`:

```powershell
docker compose exec -T -e PUB_CACHE=/state/pub-cache -w /work/packages/ctr_dart toolchain /state/sdk/tools/sdks/dart-sdk/bin/dart pub get --enforce-lockfile
docker compose exec -T -e PUB_CACHE=/state/pub-cache -w /work/packages/ctr_dart toolchain /state/sdk/tools/sdks/dart-sdk/bin/dart test
```

File/network I/O, public isolates and FFI/native packages are required by the
next compatibility milestone; the CLI does not make unsupported services work.
Dependency versions are fixed by the committed pubspec lockfile.
