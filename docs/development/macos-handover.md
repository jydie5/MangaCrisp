# macOS development handover

[日本語](macos-handover.ja.md)

This is the starting point for resuming MangaCrisp development on macOS after
the Windows work merged through PR #27. The receiving Mac must continue from
the current `origin/main`; it must not restore an older macOS checkout over the
shared files.

## Current checkpoint (2026-08-15)

- The minimum shared checkpoint is commit `9f463c0` (PR #27). This handover
  itself will make `main` a later descendant, so always use the current remote
  head rather than checking out that commit directly.
- The current macOS package is the `v0.7.1-beta` Apple Silicon prerelease.
- The current Windows package is Development Preview
  `windows-preview-0.7.1b0.4`.
- PR #27 passed the complete source suite (`99 passed, 3 skipped`), macOS source
  and package CI, and the Windows portable build, distribution audit, and
  sanitized-environment smoke test.
- The b0.4 Windows human check accepted the two-key capture controls. Windows
  capture defaults to `Alt+C` / `Alt+U`; macOS remains `Option+C` / `Option+Z`.

The macOS release asset predates PR #27. This is not a source divergence: pull
`main` before macOS work. Do not replace the existing `v0.7.1-beta` asset. A new
macOS package requires a new version/tag and a separate release decision.

## What arrived from the Windows-forward work

### Windows-only behavior

- `src/mangacrisp_app/platform/capture_windows.py` implements fixed-region
  capture and native `RegisterHotKey` handling.
- The Windows capture controller stays minimized in the taskbar while capture
  is active. macOS keeps its existing hidden-window and Dock recovery flow.
- Windows offers `Alt+C` / `Alt+U` by default and retains three-key fallbacks.
  These shortcuts do not change the macOS defaults.
- Windows packaging, provenance, validation, and preview publication remain in
  Windows-specific files. Do not rebuild or publish Windows artifacts on macOS.

### Shared behavior now on `main`

- Sequential capture and Single Page reading remain one shared product feature;
  only screen capture, global shortcuts, and window recovery differ by OS.
- `src/mangacrisp_app/cache_utils.py` now provides common PNG-cache pruning.
- PDF render and AI enhancement caches each have a 2 GiB limit. Entries unused
  for more than 30 days are pruned, while active reader files are protected.
- Reused cached pages have their modification time refreshed, providing the
  least-recently-used signal used by cleanup.
- Interrupted managed-library imports are cleaned up or restored at the next
  launch. Exact internal `.import-*` and `.backup-*` directories are handled;
  user books and capture sessions are not treated as caches.
- Capture session folders and numbered PNG files remain user-owned output and
  are never removed by automatic cache cleanup.
- The README support callout is near the download section, and
  `.github/FUNDING.yml` exposes the same optional Buy Me a Coffee link through
  GitHub's Sponsor button. Payment does not unlock features.

## Safe sync on the Mac

Start with a clean worktree. Do not use a destructive reset to discard local
Mac work.

```bash
git status --short
git fetch origin
git switch main
git pull --ff-only origin main
uv sync --extra dev --extra app
uv run pytest -q
uv run python -m mangacrisp_app.main --smoke-test
git switch -c macos/<topic>
```

If a Mac branch already contains unmerged commits, fetch `origin/main`, inspect
the diff, and rebase or merge it deliberately. Resolve shared-file conflicts by
preserving both platforms' behavior. Never choose an entire old `viewer.py`,
`bookshelf.py`, `library.py`, or `page_provider.py` as the conflict resolution.

## First macOS verification after sync

Use only the redistributable material in `demo/` and a generated color PDF.

1. Launch the bookshelf and confirm existing library metadata opens normally.
2. Open a demo archive and a color PDF. Check Spread and Single Page (`V`),
   page movement, and Original/Enhanced (`O`) without a color-to-monochrome
   transition.
3. Start sequential capture after granting Screen Recording permission. Confirm
   `Option+C` captures, `Option+Z` undoes, the controller can be restored from
   the Dock, and finishing produces ordered color PNG plus CBZ/ZIP output.
4. Open several pages with enhancement, restart the reader, and confirm cached
   results are reused. The new pruning must not remove active pages.
5. Use **Clear Cache** and confirm PDF render and AI enhancement caches can be
   regenerated while managed books remain.
6. Open Help and confirm the project and optional support links work.

If these checks pass, no macOS reimplementation of the Windows work is needed.
Record only an actual regression on a `macos/<topic>` branch; put a shared fix
on `core/<topic>`.

## Shared files that need conflict care

| File | Current responsibility |
|---|---|
| `src/mangacrisp_app/bookshelf.py` | Shared bookshelf and platform-aware capture-window recovery |
| `src/mangacrisp_app/viewer.py` | Shared reader, Single Page, correction scheduling, and AI-cache maintenance |
| `src/mangacrisp_app/library.py` | Managed imports, database state, deletion, and interrupted-import recovery |
| `src/mangacrisp_app/page_provider.py` | Lazy color PDF rendering and bounded render cache |
| `src/mangacrisp_app/cache_utils.py` | Shared size/age pruning with active-file protection |
| `src/mangacrisp_app/capture/` | Shared capture session, review, numbering, and packaging |
| `src/mangacrisp_app/platform/capture_macos.py` | macOS permission and capture integration |
| `src/mangacrisp_app/platform/capture_windows.py` | Windows capture, global hotkeys, and Windows-only presets |

Do not move Windows work into the macOS adapter or add OS conditionals to the
shared reader when a platform boundary already exists.

## Remaining release boundaries

- macOS signing and notarization remain a macOS release task.
- Windows stable release still requires Intel and AMD Vulkan evidence and a
  separate clean Windows account check. This does not block macOS source work.
- Build and validate each release artifact on its target OS.
- Tags and release assets must come from `main`; never overwrite an existing
  prerelease asset to make it represent newer source.
