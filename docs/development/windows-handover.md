# Windows development handover

This document is the starting point for continuing MangaCrisp on a Windows PC.
The Windows version must preserve the completed macOS product behavior rather
than become a separate implementation.

## Product baseline

The macOS beta is the behavioral reference:

- visual bookshelf and multi-archive drag and drop
- ZIP/CBZ, RAR/CBR, 7z/CB7, folders, and individual images
- lazy color-preserving PDF reading without extracting every page up front
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

## Current Windows checkpoint (2026-07-27)

- Phase 1 source compatibility is implemented on Windows 11 x64; all 46 shared
  and platform tests pass.
- ZIP/CBZ and 7z/CB7 demo flows pass. The pinned 7-Zip 26.02 x64 backend is
  bundled for RAR/CBR and a RAR5 solid archive was extracted through the app's
  fallback path.
- A PyInstaller one-folder development baseline bundles the audited Zig-built
  Real-CUGAN engine, passes the distribution audit, packages as a portable ZIP,
  and starts after extraction from a separate directory.
- The extracted ZIP passes the sanitized-environment smoke test with Python,
  uv, and virtual-environment paths removed. A separate clean-account test is
  still required.
- PyInstaller remains the selected first-release packager after a measured
  pyside6-deploy/Nuitka comparison. See
  `docs/development/windows-packaging-comparison.md`.
- Original-image reading remains available without the AI engine.
- The fixed-recipe Real-CUGAN validation passes on the NVIDIA GeForce RTX 2070
  SUPER (2.216 seconds for the latest fixed demo run). The pinned Zig build
  imports no Microsoft VC/OpenMP or MinGW runtime DLL and bundles its complete
  notices and provenance. The path-sanitized source report is committed and
  revalidated by the distribution audit.
- The current development account passed interactive launch, bookshelf import,
  reader rendering, and original/enhanced comparison on 2026-07-27. This does
  not replace the separate clean-account gate.
- `.github/workflows/windows-preview.yml` rebuilds and audits the exact Windows
  package on GitHub Actions. It can publish a clearly marked prerelease only
  when the engine matches the committed NVIDIA evidence and no blockers other
  than Intel, AMD, and separate clean-account validation remain.

Remaining release work is Intel/AMD coverage and a clean-account test without
development tools. Reports are registered with their evidence SHA-256 and must
match the bundled engine. See
`docs/development/windows-release-validation.md`.

## Incoming main checkpoint: macOS v0.7.0-beta (2026-08-03)

`main` now contains the macOS `v0.7.0-beta` work merged by PR #16. The Windows
`0.6.0` Development Preview remains the latest verified Windows package. Do not
describe the following changes as Windows-supported until they pass on a real
Windows x64 machine and in the Windows portable package:

- lazy PDF page rendering through pinned `pypdfium2==5.12.1`
- managed PDF import that copies the original PDF and generates only its cover
- bounded PDF render-cache cleanup when a managed PDF is removed
- database schema versioning, pre-migration backup, and newer-schema rejection
- atomic staged imports
- archive path, member-count, expanded-size, per-item-size, and compression-ratio
  limits
- diagnostics copying without local paths or book names
- user-triggered cache clearing

### Required Windows sync branch

1. Update from `origin/main` and create `windows/pdf-v0.7`.
2. Run the complete source test suite before making Windows-specific changes.
3. Verify that the pinned `pypdfium2` Windows x64 wheel installs and that its
   PDFium DLL and nested license files are included by PyInstaller and the
   distribution audit.
4. Test direct PDF opening and managed bookshelf import with the redistributable
   color fixture only. Confirm that color survives both original and enhanced
   display paths.
5. Confirm that a 300-page PDF opens without eagerly rendering or storing all
   pages and that removing a managed PDF removes only its managed copy and
   render cache.
6. Re-run ZIP/RAR/7z import checks because archive safety rules changed in
   shared code.
7. Build the one-folder portable application, audit it, and run the extracted
   sanitized-environment smoke test.
8. Record the result in this document and in
   `docs/development/windows-release-validation.md` before publishing a new
   Windows preview.

Do not modify or replace the macOS `v0.7.0-beta` release assets from the Windows
branch. Windows artifacts must be built on Windows and published under their
own Windows preview tag.

## Technology decision

Continue with PySide6 and the existing Python code for the first Windows
release. Do not port the UI to C#, C++, Rust, or a web runtime before measuring
an actual blocker.

The packaging comparison is complete:

1. PyInstaller one-folder is selected for the first release.
2. `pyside6-deploy` standalone is deferred as a later optimization experiment.

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

- Build the pinned Real-CUGAN source with the pinned Zig toolchain and copy-only
  Vulkan SDK; use the official package only for verified model files.
- Record source/submodule commits, tool and archive SHA-256 values, PE imports,
  model hashes, and all licenses in generated provenance.
- Detect engine availability without blocking bookshelf or reader startup.
- Require engine-matched Intel, AMD, and NVIDIA evidence before release.
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
- A color demo PDF opens directly and after bookshelf import without becoming
  monochrome.
- A long PDF renders pages lazily and keeps its cache within the documented
  bound.
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
