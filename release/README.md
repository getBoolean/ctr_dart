# dartbrew complete native SDK

Preview .4 is the first SDK with the `dartbrew` command-line tool. It replaces
the `ctr` tool that earlier previews shipped. `dartbrew compile` takes over the
old `build` command, and `create`, `run`, `test` and `devices` are new.

CTR, the codename of the 3DS-family platform, is the only build target. The
docs use the codename for the target and name the hardware only when stating
what it requires: this preview needs a New 3DS-family console or Azahar.

Download the SDK ZIP for your host from the
[preview .4 release](https://github.com/getBoolean/dartbrew/releases/tag/v0.1.0-preview.4):

- [Windows x64](https://github.com/getBoolean/dartbrew/releases/download/v0.1.0-preview.4/dartbrew-0.1.0-preview.4-windows-x64.zip)
- [Linux x64](https://github.com/getBoolean/dartbrew/releases/download/v0.1.0-preview.4/dartbrew-0.1.0-preview.4-linux-x64.zip) (glibc 2.36 or newer)
- [macOS Intel](https://github.com/getBoolean/dartbrew/releases/download/v0.1.0-preview.4/dartbrew-0.1.0-preview.4-macos-x64.zip)
- [macOS Apple Silicon](https://github.com/getBoolean/dartbrew/releases/download/v0.1.0-preview.4/dartbrew-0.1.0-preview.4-macos-arm64.zip)

Choose a `dartbrew-...` SDK ZIP rather than GitHub's generated source archives.
Earlier previews stay on their own release pages,
[preview .2](https://github.com/getBoolean/dartbrew/releases/tag/v0.1.0-preview.2)
and [preview .3](https://github.com/getBoolean/dartbrew/releases/tag/v0.1.0-preview.3).
Their downloads are named `ctr-dart-...` and contain the older `ctr` tool, so
the commands below do not apply to them.

Each download contains `dartbrew` (`dartbrew.exe` on Windows), a host Dart SDK,
the native Dart kernel compiler and ARMv6K AOT compiler, the GNU ARM
assembler and linker, and precompiled CTR runtime libraries. Keep the extracted
folder together. You do not install Docker, Python, PowerShell, make, Dart or
devkitARM. The host operating system's standard libraries are still required.

## Requirements

- A New 3DS-family console with
  [Luma3DS](https://github.com/LumaTeam/Luma3DS) and Homebrew Launcher, or the
  [Azahar](https://github.com/azahar-emu/azahar) emulator. The original 3DS is
  unsupported.
- For `run` and `test` on a console, the computer and console on the same local
  network.

## Commands

Extract the bundle for your operating system and CPU. On Windows, run
`.\dartbrew.exe` from the extracted folder; on macOS and Linux, run
`./dartbrew`. Add the folder to `PATH` to run `dartbrew` from anywhere, as the
examples below do. Keep projects and build output in folders outside the SDK
folder. `dartbrew help <command>` lists every option.

| Command | What it does |
| --- | --- |
| `dartbrew doctor` | Verifies every bundled tool and runtime asset. |
| `dartbrew create <directory>` | Creates a console-app project that builds, runs and tests without edits. |
| `dartbrew compile` | Builds an app and a ready-to-copy SD card folder. AOT by default. |
| `dartbrew run` | Builds the project, starts it on a device and streams its output. JIT by default. |
| `dartbrew test` | Runs the project's `package:test` files on a device and reports each test. |
| `dartbrew devices` | Lists the consoles and Azahar reachable right now. |
| `dartbrew pub`, `analyze`, `format`, `fix`, `doc`, `info` | Run the bundled Dart SDK's commands with the same arguments. |

`compile`, `run`, `test`, `create` and `devices` take `--target`, which is
`ctr` by default and is the only target in this preview. Host-only `dart`
commands such as `build` and `install` are refused with a message.

### Create and build

```console
dartbrew doctor
dartbrew create hello
cd hello
dartbrew compile --project-directory . --output ../builds/hello-aot bin/main.dart
dartbrew compile --project-directory . --mode jit --output ../builds/hello-jit bin/main.dart
```

`compile` needs a new output directory. It writes `application.3dsx`,
`artifact.json`, `run.json`, logs and intermediates in `work/`, and a prepared
`SDROOT` folder. Copy the contents of `SDROOT` to the root of the SD card and
launch the app from Homebrew Launcher. Homebrew Launcher shows the `name` and
`description` from the project's `pubspec.yaml` and a built-in icon. A top-level
`dartbrew:` map in `pubspec.yaml` can override `title`, `description`, `author`
and `icon` (a PNG path relative to the project).

`--project-directory` points at the folder with `pubspec.yaml`; without it,
`compile` uses the entrypoint's folder. The bundled Dart resolves packages.
First resolution needs network access unless the dependencies are cached;
`--offline` restricts resolution to that cache. Package resolution does not
establish compatibility with unsupported target APIs. Git dependencies and
native build hooks are unqualified in this preview.

### Run and test on a console

1. On the console, open Homebrew Launcher and press Y. The netloader waits for
   a connection.
2. From the project folder, run the program or its tests:

   ```console
   dartbrew run
   dartbrew test
   ```

dartbrew finds the console on the local network. To skip discovery, pass its
address with `-d 192.168.1.20`. `dartbrew devices` shows what it can reach. The
program's output streams to your terminal, and `dartbrew run` exits 0 when the
program finishes normally. `dartbrew test` prints one line per test and a
summary, and exits non-zero when a test fails. Use `--mode aot` to run an AOT
build, and `--timeout <seconds>` to stop a run that takes too long.

**Firewall.** The computer must allow inbound UDP and TCP on port 17491. UDP
finds the console; TCP carries the program's output back. If 17491 is taken
or blocked, pick another TCP port for the output with `--host-port <port>`.
The console side of the connection always uses 17491.

### Run and test in Azahar

```console
dartbrew run -d azahar
dartbrew test -d azahar
```

dartbrew finds Azahar from `--azahar <path>`, then the `DARTBREW_AZAHAR`
environment variable, then `azahar` on `PATH`. It writes to Azahar's emulated
SD card, found in Azahar's user folder: a portable `user/` folder if there is
one (next to the executable on Windows, in the current folder elsewhere),
otherwise Azahar's default user folder. Inside it, the custom storage folder
from Azahar's settings wins over `sdmc/`. Set `DARTBREW_AZAHAR_SDMC` to the SD
card folder if it picks the wrong one. dartbrew starts Azahar with the
app and closes it when the run ends.

### Without the netloader

Copy an app built by `compile` to the SD card instead. With FTP, transfer the
named app directory under `3ds/` first and `ctr-runtime-run.cfg` last. Launch
the app in Homebrew Launcher, then retrieve `ctr-runtime.log` from the SD root.
Keep it with the matching `run.json`; the run ID and artifact and build
identities tell that launch apart from older tests.

## Scope and evidence

The preview targets AOT and on-device JIT execution on CTR. File/network I/O,
application isolates, FFI/native packages, universal SDK compatibility and
Flutter remain unfinished. Other targets are unqualified.

Preview .4 has not been qualified yet. Until its results are recorded, the
evidence below belongs to the builds it names. All four preview .2 host bundles
passed native builds, dependency inspection and real AOT/JIT build tests from
extracted downloads with an empty PATH. Fresh AOT sample outputs from all four
hosts also passed in Azahar. Physical-console evidence applies to the
separately identified SDK32 builds. See [the native SDK notes](../docs/ctr-native-sdk.md).
This preview is unsigned; signing and macOS notarization are not configured.

## Publishing a release

The source tree builds `0.1.0-preview.4`. Its launcher and runtime assets
changed, so preview .4 must be qualified on all four hosts, a console and
Azahar before upload, with its results recorded in a `results.json` file.

Before any `gh release upload`, run the publish guard against the recorded
qualification results. It refuses archives whose version, name or SHA-256 do not
match a passing host record:

```console
python release/check_release.py --results <qualification-dir>/results.json out/*/dartbrew-*.zip
```

Producer scripts and Docker Compose are development tools, not SDK recipient
requirements. GNU corresponding source and controlling build material accompany
the assembler/linker artifacts as `source-ctr-binutils-<version>-<host>.zip`.
Preserve the SDK's notices and provenance.
