# MangaCrisp for Windows

[English](INSTALL.windows.md) | [日本語](INSTALL.windows.ja.md)

## Current status

The Windows 10/11 x64 port is a development preview. The source application and
the PyInstaller one-folder baseline run on Windows, but the public portable
release is not ready yet. In particular, the pinned Windows Real-CUGAN package,
its checksum, and its complete license bundle still need release validation.

Original-image reading remains available when the AI engine is absent.

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
uv run python scripts/build_windows_app.py
uv run python scripts/audit_windows_distribution.py
uv run python scripts/package_windows_portable.py --skip-build --development-baseline
```

The application is written to `dist\MangaCrisp\MangaCrisp.exe`. Keep the entire
`MangaCrisp` directory together; copying only the executable will not work.
The baseline ZIP is for local verification and must not be published as a
release.

## Known preview limitations

- Real-CUGAN is not bundled until the official Windows archive and all notices
  are pinned and verified.
- RAR/CBR compatibility still needs a selected redistributable extraction
  backend and license audit.
- The build is unsigned and has no installer, file associations, or updater.
- Clean-account testing without Python installed is still required before a
  public release.

Do not redistribute a development build as a MangaCrisp release.
