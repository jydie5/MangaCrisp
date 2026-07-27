# MangaCrisp for Windows

[English](INSTALL.windows.md) | [日本語](INSTALL.windows.ja.md)

## Current status

The Windows 10/11 x64 port is a development preview. The source application and
the PyInstaller one-folder baseline run on Windows, but the public portable
release is not ready yet. The baseline bundles a pinned Zig-built Real-CUGAN
engine whose source, tools, PE imports, models, licenses, and hashes are audited.
It works on the current NVIDIA test machine without a Microsoft VC/OpenMP or
MinGW runtime DLL.

Original-image reading remains available when the AI engine is absent.
RAR/CBR fallback extraction is provided by a pinned, checksum-verified 7-Zip
26.02 x64 backend whose license and provenance are included with the build.


## Run from source
Install Git and [uv](https://docs.astral.sh/uv/), then run:

```powershell
git clone https://github.com/jydie5/MangaCrisp.git
Set-Location MangaCrisp
git switch -c windows/bootstrap
uv sync --extra dev --extra app
uv run pytest
uv run mangacrisp
```

Use only the freely redistributable archives under `demo/` for development and
screenshots.

## Windows storage

- Settings and database: `%APPDATA%\MangaCrisp`
- AI and display cache: `%LOCALAPPDATA%\MangaCrisp`
- Managed reading copies: `%USERPROFILE%\MangaCrisp Library` by default

Removing a book deletes MangaCrisp's managed copy and reading state. It does not
delete the source ZIP, RAR, or 7z archive.

## Build the one-folder baseline

```powershell
uv sync --extra dev --extra app
uv run python scripts/fetch_vulkan_sdk_windows.py --accept-licenses
uv run python scripts/build_realcugan_windows.py --clean
uv run python scripts/build_windows_app.py
uv run python scripts/audit_windows_distribution.py --require-engine
uv run python scripts/package_windows_portable.py --skip-build --development-baseline
```

The application is written to `dist\MangaCrisp\MangaCrisp.exe`. Keep the entire
`MangaCrisp` directory together; copying only the executable will not work.
The baseline ZIP is for local verification and must not be published as a
release.

## Known preview limitations

- The bundled engine still needs validation on Intel and AMD Vulkan graphics.
  The application continues with original images if enhancement is unavailable.
- The build is unsigned and has no installer, file associations, or updater.
- Clean-account testing without Python installed is still required before a
  public release.

Do not redistribute a development build as a MangaCrisp release.
