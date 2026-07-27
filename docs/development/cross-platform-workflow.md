# Cross-platform development workflow

MangaCrisp uses one repository and one product version for macOS and Windows.
The goal is to share reader behavior while isolating packaging and operating
system integration.

## Repository strategy

Use short-lived branches and pull requests:

| Change | Branch prefix | Examples |
|---|---|---|
| Shared reader, library, cache, or tests | `core/` | `core/archive-contract` |
| Windows integration and packaging | `windows/` | `windows/portable-build` |
| macOS integration and packaging | `macos/` | `macos/notarization-fix` |
| Documentation only | `docs/` | `docs/windows-install` |

`main` must remain usable by both platforms. Release tags are created only from
`main`.

## Conflict prevention

1. Start from the current `origin/main`.
2. Keep platform code in platform-specific files.
3. Avoid formatting or renaming unrelated shared files.
4. Make shared API changes in a separate `core/` pull request.
5. Merge the shared pull request before platform pull requests depend on it.
6. Update the branch from `origin/main` and run tests before merging.

Typical parallel work:

- Windows PC changes `packaging/windows/` and Windows adapters.
- Mac changes `packaging/macos/`, signing, notarization, and Mac adapters.
- Either PC may change common code, but only in a dedicated `core/` branch.

## Target source layout

The current shared modules remain the source of truth. Introduce platform
boundaries only where actual behavior differs:

```text
src/mangacrisp_app/
  archive_utils.py
  bookshelf.py
  engine_utils.py
  library.py
  viewer.py
  platform/
    __init__.py
    common.py
    macos.py
    windows.py
packaging/
  macos/
  windows/
```

Do not duplicate `viewer.py`, cache scheduling, page order, quality presets, or
library metadata for Windows.

## Files that are not transferred through Git

The following are intentionally local:

- `.venv/`
- `build/` and `dist/`
- `sample/`
- the user's MangaCrisp Library
- AI caches and application settings
- signing and notarization credentials
- downloaded engine bundles before provenance verification

If a Windows developer needs a local sample, use the redistributable archives
under `demo/`.

## Pull request checklist

- Scope is one of shared, Windows, macOS, or documentation.
- Shared tests pass.
- Target-platform tests pass.
- No local absolute paths or private data are present.
- New dependencies and binaries have license and provenance records.
- User-visible behavior is documented in English and Japanese where applicable.
