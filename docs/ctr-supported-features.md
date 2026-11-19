# Current Dart CTR support

This inventory describes the 32-patch SDK on 2026-11-17, with New 3DS as the
reference device. It records tested capabilities rather than promising every
program using a library will work. The current hardware matrix contains ten
exact-artifact passes, each with successful cleanup and a terminal pass.

| Area | Current evidence | Remaining boundary |
| --- | --- | --- |
| Native AOT | Five curated programs pass on New 3DS | Wider language/library and resource coverage |
| On-device JIT | The same five programs pass on New 3DS | Wider optimization, lifecycle and compiler stress |
| CLI packaging | Self-contained native SDK builds AOT/JIT offline on four hosts with an empty PATH ([native SDK](ctr-native-sdk.md)) | Hosted pub.dev resolution and JIT execution of SDK-built apps are unqualified |
| Core language and collections | Hello, retained GC data, exception/stack and focused numeric checks | No complete language/corelib compatibility claim |
| Async/timers | Curated asynchronous work completes and cleans up in both modes | Broader timer, cancellation and long-running application coverage |
| Numeric semantics | Focused target tests plus software-helper/provider checks | Broader upstream/optimization-mode corpus; not universal numeric compatibility |
| Files/network I/O | Required next milestone | Public `dart:io` file, directory, socket, DNS and HTTP/TLS behavior is not qualified |
| Public isolates | Internal VM threading/ports support tested applications | Public isolate API, multiple-isolate semantics and resource limits are not qualified |
| FFI/native packages | Native runtime linkage and internal helper ABI checks | These are not public FFI/package qualification; dependency linking/loading and callbacks remain work |
| Flutter | Planned after universal Dart compatibility | No Flutter engine rendering or application qualification |
| Other Nintendo targets | Research scope only | Original 3DS, DS/DS Lite, Switch and Switch 2 are unqualified |

## Unsupported API failure shapes (pending device check)

`dart:io` has no CTR implementation. The launcher attaches a fallback native
resolver to `dart:io`, so calling any of it (files, directories, sockets,
processes, stdout/stdin, `exit()`, `sleep()`, `Platform`, `HttpClient`) throws
a catchable `UnsupportedError` with the text `Unsupported operation:
<NativeName> is not supported on CTR (dart:io)`, for example
`Namespace_GetDefault` for file access or `Process_Exit` for `exit()`. The run
continues, and `dartbrew test` reports an uncaught one as a failed test naming
the area. This was verified on a host VM, including AOT's lazy native linking;
the device check below confirms it on CTR.

How calls into unsupported areas fail on CTR has not been observed yet. The
table is filled in from the device check; until then every cell is pending.

| Area | Console (AOT/JIT) | Azahar (AOT/JIT) |
| --- | --- | --- |
| File read | pending | pending |
| Socket connect | pending | pending |
| `Process.run` | pending | pending |
| `Isolate.spawn` | pending | pending |
| `DynamicLibrary.open` (FFI) | pending | pending |
| `stdout.write` | pending | pending |
| `exit` | pending | pending |
| `package:test_api` probe loads and runs | pending | pending |

Procedure: build `test/programs/unsupported_apis.dart` and
`test/projects/test_probe` (with `--project-directory`) with the current CLI in
both JIT and AOT, then run each build on a New 3DS and in Azahar using the
SD-card flow. For each area, record whether the call throws a catchable error
(with its type and message), aborts the isolate, or kills the VM; the last
`try:<area>` line printed attributes a VM kill. For the probe, record whether it
loads, whether it prints `probe:passes:passed`, `probe:fails:failed` and
`probe:done`, and its peak memory in JIT and AOT with 1 MiB reserved for the
socket buffer.

## Reproducibility and evidence

The source queue is pinned in `toolchain/versions.json`; target ABI/flags are in
`toolchain/target-ctr.json`. A fresh SDK patch replay passed during consolidation.
Raw journal identity, expected output, cleanup and terminal status of the
hardware runs were checked with the runtime validator (`runtime/ctr/results.py`).

No throughput, frame-rate, battery-life, elapsed-time or peak-memory guarantee
has been measured. A diagnostic GC run observed a 32-thread resource allowance
and three startup threads on the owner's setup. The VM's normal global worker
budget is four; blocking compensation can exceed it, so this is not a strict
process-wide thread cap. Exact firmware/Luma/Homebrew Launcher versions remain
unrecorded.

The memory-region protection and input-ownership fixes are preserved as SDK
patches and launcher sources with their focused checks. Prior failed protection
and GC attempts were failures; later passing runs do not turn those attempts
into successes. Multicore cache visibility and larger concurrency and
memory/lifecycle workloads still need qualification.

Universal Dart compatibility is the next implementation milestone. It explicitly
includes working file/network I/O, public isolates, FFI and native packages;
documenting these gaps does not satisfy that milestone. Programs also remain
subject to actual hardware resources and native dependency availability.
