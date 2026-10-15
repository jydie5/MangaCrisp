# Linux development handover

[日本語](linux-handover.ja.md)

## Linux preview b0.3 validation checkpoint (2026-10-15)

The candidate uses the Ubuntu 24.04 CI package from main `6d9600f`,
[run 38709826090](https://github.com/jydie5/MangaCrisp/actions/runs/38709826090).
Its archive SHA-256 is `f95b123d2f252e4083409afeedaf890a750a837e25693eea9a5644503acb3408`.
Linux source checks pass with **187 tests, 8 skips and 5 subtests passed**.
Clean Ubuntu 24.04 and 26.04 pass installation, packaged smoke, demo reading,
bundled RAR support, CPU Vulkan enhancement and uninstallation.
The fixed engine also passes 2× enhancement on a GTX 1060 6GB.

The same package was checked on Ubuntu 26.04.1 / GNOME 50.1 / Wayland / Qt 6.11.1
with an isolated demo-only library. The user accepted the candidate on 2026-10-15
("確認しました。mainにまーじ"). This is general desktop acceptance; individual
checklist sign-offs were not reported. AMD/Intel real GPUs,
a physical X11 session, and fractional scaling are not validated by this run.
See the [validation record](../testing/linux-ux-20261015-validation.ja.md) and
[b0.3 release notes](../releases/linux-preview-0.7.1b0.3.md).

## Incoming checkpoint: Windows UX acceptance (2026-10-15)

The user accepted the Windows candidate `0.7.1b0+win.ux.20261015.2`
("問題なさそうです"). It contains the shared reader/bookshelf UX from PR #44,
the corrected-display flash fix from PR #47, and the shared
`core/managed-removal-errors` fix. Product version remains `0.7.1b0`.
This records general Windows acceptance, not individual checklist sign-offs.
Linux desktop acceptance is still required; this Windows PC cannot verify it.

This update publishes source and handover documents, not a new downloadable
release. The existing Linux preview `linux-preview-0.7.1b0.2` and Windows b0.4
downloads predate these changes. Do not relabel or overwrite those assets.

## Start from merged main

Read `AGENTS.md`, [the workflow](cross-platform-workflow.md),
[the shared UX handover](ux-maintenance-handover.md),
[INSTALL.linux.md](../../INSTALL.linux.md), and
[Linux packaging](../../packaging/linux/README.md). The
[port plan](linux-port-plan.ja.md) is historical; this checkpoint supersedes
its old test counts and packaging proposals.

First inspect `git status --short --branch`; preserve any local changes before
switching branches. Once clean:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c linux/ux-maintenance-check
uv sync --extra dev --extra app
uv run pytest -q
uv run python scripts/build_linux_app.py
```

Use a fresh branch name if that name already exists. Wait for the shared fix
to be merged before starting; do not cherry-pick the Windows integration
branch or copy Windows binaries. Build natively on Ubuntu 24.04 x86_64 using
the pinned Ubuntu engine and 7-Zip provenance. Do not change other OS packaging.

## Shared removal fix to preserve

`LibraryImportService.delete_managed_storage()` formerly suppressed storage
deletion errors. Now a managed-copy error reaches the existing per-book
failure reporting before the database entry is deleted. Missing storage is
still accepted; other books can be removed successfully. Original source
archives are never deleted. Recursive deletion is not atomic: a failed copy
may be partly removed, requiring retry or re-import from its source.
Disposable cache cleanup remains best-effort; this is not a cache transaction.

`test/test_library_removal.py` covers failures, missing storage, and normal
removal on every OS. Its actual open-file-lock test is Windows-only and must
stay skipped on Linux/macOS: POSIX can unlink an open file. Use a simulated
permission failure for that shared assertion, not a Windows lock expectation.
The Windows suite passed **186 tests, 9 skips, 5 subtests**. Linux must record
its own result; skip counts differ by platform.

## Eight native checks before the next Linux preview

Use redistributable `demo/` books or generated fixtures, never private books.
Record Ubuntu/desktop/Qt versions, Wayland or X11, GPU/driver, commit and build
identifier. Test both supported session types where available; mark gaps.

1. On GNOME Wayland and X11 separately, fullscreen cursor hides after two idle
   seconds over the image and returns on mouse/key input. It stays visible over
   overlays, menus, dialogs and during a drag. Test focus loss and return.
2. `F`, `Esc`, and the overlay Bookshelf button restore the cursor and save the
   reading position. Reopening the book resumes at the saved position.
3. Ctrl+click and Shift+click select multiple books; right-click within the
   selection keeps it, while an unselected cover becomes the sole selection.
   Check menu placement under Wayland and fractional scaling.
4. Remove two demo books with one confirmation. Keep source ZIPs unchanged;
   missing managed storage succeeds, simulated failures retain the failed
   entry and do not undo another book's successful removal.
5. Verify removal clears the corresponding PDF/enhancement cache without
   affecting another book. Locate caches through XDG paths in INSTALL.linux.md,
   not hard-coded macOS or Windows paths.
6. Confirm visible pages receive correction first, six previous pages are
   retained, and slower reading reduces forward prefetch to six then faster
   reading restores it. The median interval matters, not a single pause.
7. With enhancement on, turn a page and watch for ten seconds through prefetch
   completion: no corrected → original → corrected flash. Check color and `O`
   original/enhanced comparison too. Still screenshots alone cannot prove this.
8. Run the full suite and native package smoke test; validate the archive with
   `packaging/linux/validate-clean-ubuntu.sh` on Ubuntu 24.04 and 26.04 as
   described in the packaging README. Recheck capture permission, Alt+C/Alt+U,
   controller restore and CBZ ordering in actual Wayland/X11 desktop sessions.

If `Qt.BlankCursor` fails on a compositor, record the environment and implement
any Linux-only workaround in `src/mangacrisp_app/platform/linux.py`, not an OS
branch in shared `viewer.py`. The Linux capture adapters and portal flow were
not modified by this update. Headless CI/container checks do not establish
Wayland/X11 cursor, capture or real-GPU acceptance.

## Release notes and stopping point

After native checks, stop for a Linux human check and record the result here
before requesting a new Linux preview release. No stable-release readiness is
implied by the Windows acceptance. Keep unresolved GPU/session gaps explicit.

The next preview notes should contain these five features and two fixes:

- Fullscreen cursor auto-hide.
- Bookshelf button on the reading-information overlay.
- Bookshelf multi-select, right-click menu and batch removal.
- Visible-spread-first correction and six-page backward window.
- Reduced forward prefetch while reading slowly.
- Fix: corrected display no longer flashes to the original at prefetch completion.
- Fix: report managed-copy deletion failures and retain failed book entries.

Use the Japanese wording in the [companion handover](linux-handover.ja.md).
Publish a new Linux tag from verified `main`, attach checksums and update the
README download link only after its new artifact is available.
