# CTR Dart complete native SDK

Preview .2 provides complete native SDK downloads. The earlier source preview
requires a developer environment and is a different distribution.

Download the SDK ZIP for your host from the
[preview release](https://github.com/getBoolean/ctr_dart/releases/tag/v0.1.0-preview.2):

- [Windows x64](https://github.com/getBoolean/ctr_dart/releases/download/v0.1.0-preview.2/ctr-dart-0.1.0-preview.2-windows-x64.zip)
- [Linux x64](https://github.com/getBoolean/ctr_dart/releases/download/v0.1.0-preview.2/ctr-dart-0.1.0-preview.2-linux-x64.zip) (glibc 2.36 or newer)
- [macOS Intel](https://github.com/getBoolean/ctr_dart/releases/download/v0.1.0-preview.2/ctr-dart-0.1.0-preview.2-macos-x64.zip)
- [macOS Apple Silicon](https://github.com/getBoolean/ctr_dart/releases/download/v0.1.0-preview.2/ctr-dart-0.1.0-preview.2-macos-arm64.zip)

Choose a `ctr-dart-...` SDK ZIP rather than GitHub's generated source archives.

Each download contains `ctr` (`ctr.exe` on Windows), the native Dart kernel
compiler and ARMv6K AOT compiler, GNU ARM assembler/linker, a native Dart package
resolver, and precompiled New 3DS runtime libraries. Keep the extracted folder
together. You do not install Docker, Python, PowerShell, make, Dart or devkitARM.
The host operating system's standard libraries are still required.

## Build an app

Extract the bundle matching your operating system and CPU. From its directory,
Windows users can run these commands in their preferred terminal:

```console
.\ctr.exe doctor
.\ctr.exe build C:/projects/example/main.dart --mode aot --output C:/builds/example-aot
.\ctr.exe build C:/projects/example/main.dart --mode jit --output C:/builds/example-jit
```

On macOS and Linux:

```console
./ctr doctor
./ctr build /path/to/example/main.dart --mode aot --output /path/to/builds/example-aot
./ctr build /path/to/example/main.dart --mode jit --output /path/to/builds/example-jit
```

The output directory must be new. `doctor` verifies bundled asset checksums.
`build` produces `application.3dsx`, `artifact.json`, `run.json`, logs and
intermediates in `work/`, and a prepared `SDROOT` folder. No source SDK checkout
or runtime compilation occurs on the recipient's machine.

For package projects, pass `--project-directory` pointing at the directory with
`pubspec.yaml`. The bundled native resolver runs `pub get`. First resolution
needs network access unless the dependencies are cached; `--offline` restricts
resolution to that cache. No separate Dart installation is used. Package
resolution does not establish compatibility with unsupported target APIs.
Git dependencies and native build hooks are unqualified in this preview.

## Launch on New 3DS

Use a New 3DS with Luma3DS and Homebrew Launcher. Copy the contents of `SDROOT` to
the SD card. With FTP, transfer the named app directory under `3ds/` first and
`ctr-runtime-run.cfg` last. Launch that app in Homebrew Launcher, then retrieve
`ctr-runtime.log` from the SD root. Keep it with the matching `run.json`; the
run ID and artifact/build identities distinguish that launch from older tests.

A new build and its successful packaging do not prove it ran on the console.
Hardware results apply only to the earlier, separately identified SDK32 builds.

## Scope and development

The preview targets AOT and on-device JIT execution on New 3DS. File/network I/O,
application isolates, FFI/native packages, universal SDK compatibility and
Flutter remain unfinished. Other Nintendo targets are unqualified.

All four host bundles passed native builds, dependency inspection and real
AOT/JIT build tests from extracted downloads with an empty PATH. Fresh AOT
sample outputs from all four hosts also passed in Azahar. Physical-console
evidence applies to the separately identified SDK32 builds. See
[the native SDK notes](../docs/ctr-native-sdk.md). This preview is unsigned; signing
and macOS notarization are not configured.

## Publishing a release

The source tree now builds `0.1.0-preview.3`. Preview .2 bytes cannot be rebuilt
from it because the GNU source asset name sealed in each SDK changed to
`source-ctr-binutils-<version>-<host>.zip`. Preview .3 must be re-qualified on all
four hosts before upload, with its qualification results recorded in a
`results.json` file.

Before any `gh release upload`, run the publish guard against the recorded
qualification results. It refuses archives whose version, name or SHA-256 do not
match a passing host record:

```console
python release/check_release.py --results <qualification-dir>/results.json out/*/ctr-dart-*.zip
```

Producer scripts and Docker Compose are development tools, not SDK recipient
requirements. GNU corresponding source and controlling build material accompany
the assembler/linker artifacts. Preserve the SDK's notices and provenance.
