# MangaCrisp for Windows

[English](INSTALL.windows.md) | [日本語](INSTALL.windows.ja.md)

## Current status

The Windows 10/11 x64 port is available as a public Development Preview. It is
not the stable Windows release because Intel, AMD, and separate clean-account
evidence is still pending. The preview bundles a pinned Zig-built Real-CUGAN
engine whose source, tools, PE imports, models, licenses, and hashes are audited.
It works on the current NVIDIA test machine without a Microsoft VC/OpenMP or
MinGW runtime DLL.

Original-image reading remains available when the AI engine is absent.
RAR/CBR fallback extraction is provided by a pinned, checksum-verified 7-Zip
26.02 x64 backend whose license and provenance are included with the build.
Version 0.7 also bundles PDFium for lazy, color-preserving PDF reading. Its DLL
and complete nested license set are required by the distribution audit.

## Download the Development Preview

[Download MangaCrisp 0.7.0b0 Windows x64 portable preview](https://github.com/jydie5/MangaCrisp/releases/download/windows-preview-0.7.0b0.1/MangaCrisp-0.7.0b0-windows-x64-portable-preview.zip)

1. Download the ZIP.
2. Extract the complete `MangaCrisp` folder.
3. Double-click `MangaCrisp.exe`.
4. If Windows shows a security warning for the unsigned preview, confirm the
   download URL or attached SHA-256 checksum. Choose **More info** and
   **Run anyway** only if the ZIP came from the official `jydie5/MangaCrisp`
   release.

The release also includes the SHA-256 checksum, distribution audit, and
portable manifest.

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
- AI, PDF, and display cache: `%LOCALAPPDATA%\MangaCrisp`
- Managed reading copies: `%USERPROFILE%\MangaCrisp Library` by default

Removing a book deletes MangaCrisp's managed copy, PDF render cache, and reading
state. It does not delete the source PDF, ZIP, RAR, or 7z archive.

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

Maintainers can create the separately named public preview with:

```powershell
uv run python scripts/package_windows_portable.py --skip-build --development-preview
```

The preview command accepts only the documented Intel, AMD, and clean-account
release blockers. It rejects an engine that does not match the committed
NVIDIA evidence.

## Known preview limitations

- The bundled engine still needs validation on Intel and AMD Vulkan graphics.
  The application continues with original images if enhancement is unavailable.
- The build is unsigned and has no installer, file associations, or updater.
- Clean-account testing without Python installed is still required before the
  stable Windows release.

Do not represent the Development Preview as the stable Windows release.
