# Linux development handover

[日本語](linux-handover.ja.md)

## macOS beta 0.7.1b0.5 release checkpoint (2026-10-25)

The user accepted the Apple Silicon macOS candidate for release. A new
[`macos-beta-0.7.1b0.5`](../releases/macos-beta-0.7.1b0.5.md) tag/release is
published from main `b062dda`. It contains the shared `7605b64`
reading-records runtime—status filters/bulk actions, same-library JSON
backup/restore, bookmark labels/notes, same-ID reimport-history preservation
and the declarative reader shortcut registry—plus release documentation. Comic
EPUB remains unconnected and is not a reading feature.

The macOS source suite recorded **414 passed, 8 skipped, and 12 subtests
passed**. The packaged target-Mac candidate passed ad-hoc signature, startup
and color-PDF smoke checks, real-GPU color correction, and actual-app
navigation, overview, Help (`H`) and fullscreen (`F`) checks. Earlier candidate
coverage also includes status bulk actions, backup preview/cancel/restore,
bookmark-note editing and same-ID reimport history preservation. This is not
Linux desktop or hardware evidence. Keep Linux Preview b0.4 unchanged; a Linux
release still requires a target-OS build and separate Wayland/X11, scaling,
native-dialog/focus, portal, real-GPU and clean-install acceptance.

## Reading-records continuation after Windows b0.7 (2026-10-25)

PRs #77–#81 are now merged to main in dependency order. The Windows user accepted
the integrated candidate and
[Windows Preview 0.7.1b0.7](https://github.com/jydie5/MangaCrisp/releases/tag/windows-preview-0.7.1b0.7)
is published from main tag target `81e7721`. It reuses the accepted Windows CI
ZIP from source `7605b641e6c6bffb672c06e5ae9787ab7aadd6b3`, without recompilation.
The ZIP SHA-256 is `3ef9961d6844811b54b535adfacc8588f8d2598a70074d12733b5be15df7f4ec`.
Local Windows tests passed 413 tests, 9 skips and 12 subtests. This is not Linux
desktop or hardware acceptance, and the Windows ZIP must not be used on Linux.

Linux preview b0.4 is unchanged and does not contain these reading-record features.
Start clean from latest main with `git pull --ff-only origin main`, then create
a fresh `linux/<topic>` branch. No feature-branch cherry-picks are needed.

- Native [Ubuntu CI 40167591018](https://github.com/jydie5/MangaCrisp/actions/runs/40167591018)
  passed on the integrated source. Its `mangacrisp-linux-x86_64` artifact was
  available on 2026-10-25. Compare source, package scripts and checksums with
  current main; reuse it if equivalent, otherwise build on Ubuntu 24.04 x86_64.
- In a demo-only library, check Unread/Reading/Completed filters with search,
  visible-selection bulk actions and completion surviving rereading. Mark unread
  resets position but must retain bookmarks, per-book settings and history.
- Check `Shift+B` label/note edit, save and Escape cancellation. Test export,
  restore preview/cancel/confirm and repeated restore without bookmark duplication.
  Confirm the overwrite prompt for a filename whose added JSON suffix already
  exists. Keep real titles/notes and backup JSON out of public issues.
- Backups are limited to 16 MiB and existing IDs in the same library. They do
  not migrate books across PCs or reconnect moved files. Existing bookmark
  labels/notes remain; restore only adds missing bookmarked pages.
- Reimport a previously read demo with the same ID and verify completion,
  last-opened history, position and bookmark notes remain. A renamed/moved
  source with a different ID is not the same case.
- Check Wayland and X11, native save/open dialogs, focus/Escape, English/Japanese
  minimum-size layout, scaling, capture/portal and real GPU behavior separately.
  Record source/artifact hash and environment, then stop for the Linux human
  check before requesting a new Linux preview. Windows acceptance is not a
  substitute; keep untested GPU/session/clean-install gates explicit.

See [reading-record semantics and checklist](reading-records-handover.md).
This update publishes Windows only; it does not change Linux download links.

## Linux-only continuation after Windows Preview b0.6 (2026-10-25)

[Windows Preview 0.7.1b0.6](https://github.com/jydie5/MangaCrisp/releases/tag/windows-preview-0.7.1b0.6)
is published. Its tag targets main `742e6b4`; it reuses the unchanged native
Windows CI ZIP from [run 40057157576](https://github.com/jydie5/MangaCrisp/actions/runs/40057157576),
tested merge `47f0c2c388de6c87e89fef76100c04f82838779d`. Runtime sources,
dependencies and Windows packaging match the macOS b0.4/main baseline
`cdab340`; subsequent changes are release/download documentation only.
Windows ZIP SHA-256 is
`54596edeec782990b18fc95bdd0b0087145c0595afc9c1b38944f50a544a6187`.
It is a reference for provenance, never a Linux executable to distribute.

The Windows user confirmed startup, `T` overview selection/page navigation,
`+` zoom and `0` fit, then approved publication. Sanitized extracted startup
was repeated locally. These are bounded Windows checks, not Linux acceptance,
an agent visual inspection, all-GPU coverage, or a clean-account certification.
Windows remains unsigned with Intel/AMD and separate clean-account gates open.

Only the Linux handover is being continued after this Windows release; no
macOS or Windows handover rewrite and no Linux release is part of this update.
The Linux download remains **linux-preview-0.7.1b0.4**, from the older
`d7bbf50` baseline; it does not contain the newest navigation/overview work.

### Receiving Linux work

1. Preserve local changes; once clean, switch to main, run
   `git pull --ff-only origin main`, then create a fresh `linux/<topic>` branch.
   Do not cherry-pick the Windows documentation branch.
2. Native Ubuntu [CI run 40057157588](https://github.com/jydie5/MangaCrisp/actions/runs/40057157588)
   already passed source and package jobs for the same integrated candidate.
   Its `mangacrisp-linux-x86_64` artifact was still available on 2026-10-25.
   Compare its tested source with the new main, verify its checksums and
   provenance, and reuse it if there is no runtime/packaging difference.
   Rebuild on Ubuntu 24.04 x86_64 if relevant source differs or it has expired;
   do not recompile merely because the handover changed.
3. With demos/generated data, check bookshelf search/sort, page-number jump,
   `B`/`Shift+B`, per-book settings restore, `+`/`-`/`0`/`W`/`1`, Ctrl+wheel
   and drag-pan without an unintended page turn. Check `T` open, visible
   thumbnails, select, cancel and close; preserve lazy PDF/ZIP behavior.
4. Record GNOME Wayland and X11 separately, scaling, Qt, Ubuntu, GPU/driver,
   source commit and artifact hash. Recheck cursor/focus/modal behavior,
   original/enhanced color, correction cache cleanup and capture/portal recovery.
   A CI/headless result is not desktop or real-GPU acceptance.
5. Run the source suite and native package/startup checks, plus clean Ubuntu
   24.04/26.04 validation as described in the Linux packaging README. Keep
   Intel/AMD, unavailable sessions and other gaps explicit.
6. Stop for the Linux human check. Record its actual scope here, then publish
   a **new Linux preview tag** only with release authorization. Retain old
   releases, attach checksums and update Linux download links after publication.

The earlier dated checkpoints below remain historical evidence; they do not
replace this Linux acceptance work. EPUB reading is still outside the release.

## Incoming macOS beta 0.7.1b0.4 checkpoint (2026-10-24)

The current Apple Silicon download is
[`macos-beta-0.7.1b0.4`](../releases/macos-beta-0.7.1b0.4.md). It carries the
shared bookshelf discovery, physical page jump, bookmark, per-book state,
zoom/pan, lazy page-overview, and processed-page/ZIP-isolation work. Comic
EPUB reading is not in that package.

The existing Linux preview is unchanged. Do not call it equivalent to the new
macOS beta. Before a Linux update, build current `origin/main` on Ubuntu and
record source and package results separately. Test both Wayland and X11,
fractional scaling, Ctrl+wheel, drag-pan, `T` overview select/cancel/close,
real GPU behavior, and the portal/capture flow. The macOS result of 367 passed,
8 skipped, 12 subtests and general macOS acceptance are not Linux acceptance.
Read the [next-features handover](next-features-handover.md) and
[shared UX handover](ux-maintenance-handover.md) before integrating.

## Source checkpoint of the existing Linux preview: PR #53/#54 (2026-10-20)

This records the existing Linux preview, not the new shared-source baseline.
For a new Linux build, use current `origin/main` as described above. This package
source includes the reader, bookshelf, correction and cache work from PR #53/#54.
The UI release line is [35f2936](https://github.com/jydie5/MangaCrisp/commit/35f2936),
and the package source checkpoint is [d7bbf50](https://github.com/jydie5/MangaCrisp/commit/d7bbf50).
The current Linux Development Preview is
[linux-preview-0.7.1b0.4](../releases/linux-preview-0.7.1b0.4.md), built from
`main` at `d7bbf50`. Its native CI run is
[39335510308](https://github.com/jydie5/MangaCrisp/actions/runs/39335510308),
and its archive SHA-256 is
`5b48794d7b75b6edd9be34c7aeea09eaecb7a5319fe0f41ddcc874c08d503ed7`.
The earlier b0.3 artifact predates the current reader controls,
shortcut-help modal, and correction/cache lifecycle; it remains available as
historical rollback material and was not overwritten.
The release note uses the clean demo gallery and
[capture procedure](../images/README.md).

Native macOS UI checks passed. The automated macOS source suite recorded
**274 passed, 8 skipped and 12 subtests passed**. The b0.4 source and packaged
startup checks are recorded in its release notes. The previous 2026-10-20 user
report that this current UI worked on a real Linux machine is a general native
success report; it does not provide Linux session, GPU/driver, scaling,
package-smoke, or per-checklist evidence. Those granular Linux gates remain
pending where evidence is absent. See the [shared UX handover](ux-maintenance-handover.md)
for cross-platform context; this document is the Linux gate and environment record.

Current behavior to verify on Linux:

- The reader has no persistent bottom toolbar. A center click opens the
  translucent reading-controls pane. Its backdrop closes the pane without
  turning the page.
- H or ? opens the shortcut-help modal. Its translucent backdrop consumes
  outside clicks; the close button, Esc, or a click outside the card closes it.
  The dismissal click must not reach the reader. The close button starts focused
  and focus returns to the reader after the dialog closes.
- The bookshelf uses scoped dark navy/teal styling, a clear library count and
  selection state, a primary Read action, and secondary file/folder/capture
  actions. Existing import, context-menu, multi-selection and deletion behavior
  remains part of the native check.

Correction and cache behavior to verify:

- models-pro runs with explicit -c 1 (syncgap 1), and its parameter key includes
  _syncgap1. An old models-pro cache key must not be reused; the SE key
  remains compatible.
- CorrectionQueue prioritizes visible/current pages, protects one in-flight
  output, and drops duplicate work at completion. Generation/settings changes,
  reader close and navigation invalidate stale completions. A failed prefetch
  stays paused while the reader is still, then a move or settings change retries.
- CorrectionDiskCache and DisplayCache reuse completed outputs when backtracking.
  Missing processed paths are queued again. Size/age pruning protects visible,
  pending, in-flight and staging-parent paths; external processed originals are
  not deleted. A prefetch completion must not flash corrected → original →
  corrected.

### Remaining Linux environment checks

Run these on X11 and Wayland separately, including fractional scaling, and
record Ubuntu/desktop/Qt versions, GPU/driver, commit and build identifier:

1. Confirm center-click controls, no persistent bottom bar, translucent modal
   alpha, outside-click dismissal, Esc handling, initial focus and focus return.
2. Turn pages forward and backward with enhancement enabled, revisit a distant
   page, and compare original/enhanced views. Confirm visible-first correction,
   retry after a correction error, stale completion cancellation, and no flash.
3. With a real models-pro run, confirm -c 1 writes _syncgap1, an old pro-key
   image is ignored, SE output is reusable, deleted processed paths regenerate,
   and active/staging outputs survive pruning without touching source archives.
4. Check the bookshelf at roughly 900x620 and fractional scaling: count,
   selection, primary Read action, import/capture actions, multi-select,
   right-click targeting and managed deletion must remain usable.
5. Run the full suite and native package smoke test; record Linux skips and
   subtests separately from the accepted macOS result.

The preview's CI checks do not supply the environment-specific evidence above.
Those checks remain unreported despite the previous general native success
report. A headless run or the old b0.3 Wayland result cannot establish
X11/Wayland layout, modal alpha, focus, correction navigation or cache behavior.

## Historical Linux preview b0.3 validation checkpoint (2026-10-15)

[Linux preview b0.3](https://github.com/jydie5/MangaCrisp/releases/tag/linux-preview-0.7.1b0.3)
is published with its archive and `SHA256SUMS.txt`. It uses the Ubuntu 24.04 CI package from main `6d9600f`,
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
This historical result does not validate the current PR #53/#54 source. The
current b0.4 preview supersedes b0.3 as the downloadable Linux preview, while
b0.3 remains available as an unchanged historical rollback artifact. The
2026-10-20 general success report is retained separately from these package
records.
See the [validation record](../testing/linux-ux-20261015-validation.ja.md) and
[b0.3 release notes](../releases/linux-preview-0.7.1b0.3.md).

## Incoming checkpoint: Windows UX acceptance (2026-10-15)

The user accepted the Windows candidate `0.7.1b0+win.ux.20261015.2`
("問題なさそうです"). It contains the shared reader/bookshelf UX from PR #44,
the corrected-display flash fix from PR #47, and the shared
`core/managed-removal-errors` fix. Product version remains `0.7.1b0`.
This records general Windows acceptance, not individual checklist sign-offs.
Linux desktop acceptance is still required; this Windows PC cannot verify it.

That Windows handover updated source and documents only. Linux b0.3 was
subsequently published with those earlier UX fixes, as recorded above; it still
predates PR #53/#54. Windows b0.4 remains unchanged. Do not relabel old assets.

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

## Current preview and stopping point

The b0.4 preview is published from verified `main`; no stable-release
readiness is implied. Keep unresolved GPU/session gaps explicit and record any
future environment-specific evidence here before requesting another preview.

The b0.4 package also retains these earlier improvements (see the historical
b0.3 release notes for their original validation):

- Fullscreen cursor auto-hide.
- Bookshelf button on the reading-information overlay.
- Bookshelf multi-select, right-click menu and batch removal.
- Visible-spread-first correction and six-page backward window.
- Reduced forward prefetch while reading slowly.
- Fix: corrected display no longer flashes to the original at prefetch completion.
- Fix: report managed-copy deletion failures and retain failed book entries.

Use the Japanese wording in the [companion handover](linux-handover.ja.md).
For a future Linux preview, publish a new tag from verified `main`, attach
checksums and update the README download link only after its new artifact is
available.
