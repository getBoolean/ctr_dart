# dartbrew

Build, run and test Dart programs as homebrew apps.

`dartbrew` is a command-line tool shaped like `dart`. It builds an ordinary Dart
program for a homebrew target, and can run it or its `package:test` tests on a
device with one command that streams the results back to your terminal. CTR,
the codename of the 3DS-family platform, is the only target so far: apps are
`.3dsx` files for Homebrew Launcher on New 3DS-family consoles. They run the real Dart VM on the console's
ARM11 CPU, in either of two modes:

- **AOT:** the program is compiled to ARMv6K machine code on your computer.
- **JIT:** the Dart VM compiles the program on the console itself.

> **Status: experimental preview.** Core Dart works on hardware: the language,
> `dart:core`, `dart:async`, `dart:collection`, garbage collection, exceptions
> and stack traces. File and network I/O, isolates, FFI and Flutter do not work
> yet. See [what is supported](docs/ctr-supported-features.md).

## Requirements

- **Device:** a New 3DS-family console running
  [Luma3DS](https://github.com/LumaTeam/Luma3DS) and Homebrew Launcher, or the
  [Azahar](https://github.com/azahar-emu/azahar) emulator. Testing so far used a
  New 3DS. The original 3DS is unsupported.
- **Computer:** Windows x64, Linux x64 (glibc 2.36 or newer), or macOS on Intel
  or Apple Silicon.

The SDK download is self-contained. You don't need Dart, Docker, Python,
devkitARM or a cross compiler installed.

## Quick start

1. Download the `dartbrew-...` SDK ZIP for your computer from the
   [releases page](https://github.com/getBoolean/dartbrew/releases) and extract
   it. Keep the extracted folder together, keep your projects outside it, and
   add it to `PATH` (or call
   `.\dartbrew.exe` on Windows and `./dartbrew` on macOS and Linux from that
   folder).

2. Check the SDK and create a project:

   ```console
   dartbrew doctor
   dartbrew create hello
   cd hello
   ```

3. On the console, open Homebrew Launcher and press Y to start the netloader.
   Then run the program or its tests from the project folder:

   ```console
   dartbrew run
   dartbrew test
   ```

   Output streams to your terminal. Allow inbound UDP and TCP port 17491 through
   your computer's firewall, or pick another TCP port with `--host-port`. Use
   `-d azahar` to run in Azahar instead.

4. To build an app to copy by hand, use `compile`. The output directory must not
   already exist:

   ```console
   dartbrew compile --project-directory . --output ../builds/hello bin/main.dart
   ```

   Copy the contents of the output's `SDROOT` folder to the root of your SD card
   and launch the app from Homebrew Launcher.

`dartbrew compile` replaces `ctr build` from earlier previews, and the `ctr`
command is gone. `dartbrew pub`, `analyze`, `format`, `fix`, `doc` and `info`
run the bundled Dart SDK. See the [SDK guide](release/README.md) for every
command, Azahar setup and the SD card flow.

## Building from source

Maintainers build the patched Dart SDK, the runtime and the per-host SDK
downloads with a pinned Docker Compose toolchain and GitHub Actions. Start with
the [runtime runbook](docs/runbooks/ctr-runtime.md),
the [Compose setup](docs/ctr-compose.md) and the
[native SDK overview](docs/ctr-native-sdk.md).

Layout:

| Path | Contents |
| --- | --- |
| `packages/dartbrew` | The `dartbrew` command-line tool. |
| `toolchain` | Dart SDK pins, the CTR patch queue and the SDK build scripts. |
| `runtime/ctr` | The launcher that embeds the Dart VM on the console. |
| `release` | Scripts that build and package the per-host SDK downloads. |
| `test/programs` | Sample programs used for hardware checks. |

## License and credits

This project is licensed under the [BSD 3-Clause License](LICENSE). The SDK
downloads bundle third-party software under its own licenses, including GNU
binutils (GPL). [CREDITS.md](CREDITS.md) lists every component and its license.
The binutils corresponding source is published with each release.

## Trademarks

This is an unofficial project, not affiliated with, endorsed or sponsored by
Nintendo. Nintendo 3DS and New Nintendo 3DS are trademarks of Nintendo. Dart is
a trademark of Google LLC. These names are used only to describe compatibility.
