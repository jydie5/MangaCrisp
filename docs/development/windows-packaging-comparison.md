# Windows packaging comparison

Measured on 2026-07-27 on the Windows x64 development machine. Both builds used
Python 3.13.6 and PySide6 6.11.1. Times and sizes are engineering measurements,
not guarantees for other machines.

## Result

Keep PyInstaller one-folder as the first Windows portable release path.
`pyside6-deploy` remains a later optimization experiment.

| Metric | PyInstaller one-folder | pyside6-deploy standalone |
|---|---:|---:|
| Builder | PyInstaller 6.20.0 | Nuitka 4.0 via pyside6-deploy, Zig 0.16.0 |
| Build time | about 42.5 s | about 7 min 35 s |
| Files | 289 | 109 |
| Directory size | 138,895,520 bytes | 202,330,448 bytes |
| Main EXE size | 5,629,337 bytes | 29,287,424 bytes |
| Isolated `--smoke-test` | 1.026 s | 2.143 s |
| PE machine | AMD64 (`0x8664`) | AMD64 (`0x8664`) |
| PE subsystem | GUI (2) | Console (3) |

The PyInstaller measurement includes the pinned 7-Zip backend, all notices, and
public Windows documentation. The Nuitka measurement is only the generated
standalone application, so its larger size is not caused by those additional
release files.

## pyside6-deploy conditions

The official Qt deployment tool generated a Nuitka standalone build and the
result passed the isolated application smoke test. The machine did not have
MSVC `dumpbin`, so pyside6-deploy warned that Qt binary dependency inspection
was skipped. Source scanning still found Qt Core, Gui, and Widgets.

Python 3.13 could not use Nuitka's MinGW64 route. The comparison therefore used
Nuitka 4.0 with the Windows x64 Zig backend and these extra arguments:

```text
--zig --assume-yes-for-downloads --windows-console-mode=disable
```

Despite the console-disable argument, the resulting Nuitka 4.0/Zig executable
had PE subsystem 3 (Windows Console). This does not meet MangaCrisp's
no-console-window acceptance criterion. A future comparison may retest a newer
Nuitka patch release with MSVC Build Tools and `dumpbin`, but that is not a
release blocker for the working PyInstaller path.

## PyInstaller release evidence

The audited PyInstaller development artifact is:

- File: `MangaCrisp-0.5.0b0-windows-x64-portable-baseline.zip`
- Size: 58,885,770 bytes
- SHA-256: `67f7ddeac1439c2d8027a5d19e1aeb895b00b8d1c751d09ed56ef587a378a546`
- Archive entries: 289
- Extracted-copy smoke test: passed
- Distribution audit: `baseline_ready=true`, `release_ready=false`

The release-ready flag remains false only because the Windows Real-CUGAN
runtime redistribution route is not approved and clean-machine/GPU coverage
is incomplete.
