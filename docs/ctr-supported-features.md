# Current Dart CTR support

This inventory describes the 32-patch SDK on 2026-11-17, with New 3DS as the
reference device; the 2026-11-19 console results below add the 33-patch
launcher work, and 2026-11-20 adds Azahar 2126.2 (AOT). It records tested capabilities rather than promising every
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

## Unsupported API failure shapes

`dart:io` has no CTR implementation. The launcher attaches a fallback native
resolver to `dart:io`, so calling any of it (files, directories, sockets,
processes, stdout/stdin, `exit()`, `sleep()`, `Platform`, `HttpClient`) throws
a catchable `UnsupportedError` with the text `Unsupported operation:
<NativeName> is not supported on CTR (dart:io)`. The run continues, and
`dartbrew test` reports an uncaught one as a failed test naming the area.

Observed on a New 3DS on 2026-11-19 with `test/programs/unsupported_apis.dart`,
run through `dartbrew run` with the schema-2 launcher. AOT and JIT behaved the
same. On 2026-11-20 the same probe ran in Azahar 2126.2 (Windows, MSVC build) in
AOT and gave identical results.

Azahar runs AOT only. The JIT VM publishes compiled code with Luma3DS's custom
cache SVC; Azahar doesn't emulate it (`svcGetSystemInfo(0x10000)` fails) and the
VM aborts right after `begin`. `dartbrew run -d azahar` and `test -d azahar`
therefore default to AOT and refuse `--mode jit`. The hello, async, exceptions
and gc_stress fixtures pass in Azahar AOT through `dartbrew run --verdict`.

| Area | Console (AOT and JIT) | Azahar |
| --- | --- | --- |
| File read | Catchable `UnsupportedError`: `Namespace_GetDefault` | Same (AOT) |
| Socket connect | Catchable `UnsupportedError`: `InternetAddress_Parse` | Same (AOT) |
| `Process.run` | Catchable `UnsupportedError`: `Platform_OperatingSystem` | Same (AOT) |
| `Isolate.spawn` | Catchable `UnsupportedError`: `Isolate.spawn` | Same (AOT) |
| `DynamicLibrary.open` (FFI) | Catchable `ArgumentError`: loading dynamic libraries is not supported | Same (AOT) |
| `stdout.write` | Catchable `UnsupportedError`: `File_GetStdioHandleType` | Same (AOT) |
| `exit` | `UnsupportedError`: `Process_Exit`. Uncaught, so the run ends as fail with a full stack trace | Same (AOT) |
| `package:test` files with `dartbrew test` | Run and report per test in AOT and JIT. An 18.9 MB JIT test app uploads once Wi-Fi interference is reduced | Run and report per test in AOT, with full stack traces; a fresh `dartbrew create` project passes |

`Uri.base` is `file:///` on CTR (SDK patch 0033, installed by the launcher), so
`package:path` and `package:stack_trace` work and failing tests report full
stack traces. Confirmed on the console on 2026-11-19 with the 33-patch tree.

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
