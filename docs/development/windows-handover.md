# Windows development handover

This document is the starting point for continuing MangaCrisp on a Windows PC.
The Windows version must preserve the completed macOS product behavior rather
than become a separate implementation.

## Product baseline

The macOS beta is the behavioral reference:

- visual bookshelf and multi-archive drag and drop
- ZIP/CBZ, RAR/CBR, 7z/CB7, folders, and individual images
- right-bound manga reading with a single cover and two-page spreads
- one-page alignment correction
- natural title and volume ordering
- continue to the next volume while retaining full screen
- translucent progress overlay
- original/enhanced comparison
- automatic Real-CUGAN processing around the reading position
- adaptive forward prefetch and a revolving backward cache
- simple quality modes and saved manual presets
- English and Japanese UI

Do not redesign these workflows during the first Windows port.

## Initial Windows target

- Windows 10 and Windows 11
- x86-64
- portable ZIP distribution
- no Python, uv, CUDA, or installer required by the end user
- `MangaCrisp.exe` launches by double-click
- bundled `realcugan-ncnn-vulkan.exe` and verified models
- Intel, AMD, and NVIDIA Vulkan-capable graphics
- immediate original-image viewing when enhancement is unavailable or behind
- optional CPU engine mode only after its user experience is measured

Windows on ARM, a native installer, file associations, CUDA-specific builds,
and automatic updates are later work.

## Technology decision

Continue with PySide6 and the existing Python code for the first Windows
release. Do not port the UI to C#, C++, Rust, or a web runtime before measuring
an actual blocker.

Compare these packaging candidates on Windows:

1. PyInstaller one-folder for the quickest compatible baseline.
2. `pyside6-deploy` standalone for startup time and package-size optimization.

Do not use one-file packaging for the first release. Qt and the AI models are
better kept as visible application files, and one-file extraction can delay
startup.

## First setup on Windows

1. Install Git and uv.
2. Clone `https://github.com/jydie5/MangaCrisp.git`.
3. Read `AGENTS.md`.
4. Create a branch named `windows/bootstrap`.
5. Run `uv sync --extra dev`.
6. Run `uv run pytest`.
7. Run the source application before adding packaging.

Use only the freely redistributable books in `demo/` for development,
screenshots, and automated checks.

## Implementation order

### Phase 1: source compatibility

- Make the existing source application launch on Windows.
- Add platform adapters for storage paths, opening folders and URLs, full
  screen behavior, and process creation flags.
- Preserve all shared reader tests.

### Phase 2: archive and library validation

- Validate ZIP/CBZ and 7z/CB7.
- Select and license-audit the RAR/CBR extraction path.
- Confirm batch import, deletion of managed copies, and preservation of source
  archives.
- Use a Windows user-data directory for settings/cache and a user-visible or
  user-selected location for the managed library.

### Phase 3: AI engine

- Download a pinned official Windows Real-CUGAN ncnn Vulkan release.
- Record source URL, release identifier, SHA-256, and all licenses.
- Detect engine availability without blocking bookshelf or reader startup.
- Verify Intel integrated graphics, AMD, and NVIDIA where test machines are
  available.
- Retain original-image fallback when Vulkan or the engine fails.

### Phase 4: portable release

- Build a one-folder application.
- Remove unused Qt modules and plugins.
- Create `MangaCrisp-<version>-windows-x64-portable.zip`.
- Audit the ZIP for local paths, private data, unlicensed binaries, and missing
  notices.
- Test on a clean Windows account without Python installed.

## Acceptance checks

- ZIP extraction followed by double-click starts the application.
- First bookshelf paint is not blocked by engine discovery.
- A demo ZIP imports and opens.
- Right-bound page order and all keyboard shortcuts match macOS.
- Original pages remain responsive when AI processing is behind.
- Direction changes reuse nearby caches rather than restarting all work.
- Full screen remains active when moving to the next volume.
- Removing a book deletes only the managed copy.
- No Python console window appears during normal operation.

## Files to add on the Windows branch

Expected first additions:

```text
src/mangacrisp_app/platform/windows.py
packaging/windows/
scripts/build_windows_app.py
scripts/audit_windows_distribution.py
INSTALL.windows.md
INSTALL.windows.ja.md
```

Keep Windows build outputs in `dist/`; they are release artifacts and must not
be committed.
