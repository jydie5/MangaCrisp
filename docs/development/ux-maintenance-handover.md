# Reader and bookshelf UX handover (macOS-first)

[日本語](ux-maintenance-handover.ja.md)

## macOS beta 0.7.1b0.4 release follow-up (2026-10-24)

[`macos-beta-0.7.1b0.4`](../releases/macos-beta-0.7.1b0.4.md) is the current
Apple Silicon release. Its tag is the source reference; the exact final main
commit belongs in the release metadata rather than this handover. It includes
bookshelf discovery, physical page jumps, bookmarks, per-book state restore,
zoom/pan, lazy page overview, and lazy processed-page lookup with ZIP-page
isolation. Comic EPUB reading is outside this release.

The integrated macOS suite recorded **367 passed, 8 skipped, 12 subtests**.
The local test package passed its distribution audit, startup smoke, and UI
check; the user gave general acceptance. This is not evidence for an updated
Windows or Linux package. Their current downloads remain unchanged. Before a
future platform release, build on the target OS and check scaling, keyboard
focus, Ctrl+wheel (Windows/Linux), drag-pan, overview cancellation, real GPU,
and on Linux both Wayland and X11. The macOS package remains ad-hoc signed and
not notarized.

The detailed continuation checklist is in the
[next-features handover](next-features-handover.md). The clean screenshot
gallery now includes the page overview and is documented in
[the capture procedure](../images/README.md).

## Previous UI release baseline (2026-10-20)

PR #53 (correction/cache) and PR #54 (reader/bookshelf UI) are merged into
`main`; the UI release line is `35f2936`, and that release used main handover
`d7bbf50`. Apple Silicon beta `macos-beta-0.7.1b0.3` is published. The UI
implementation checkpoint is `97dc06f`, with portable font-metric tests at
`ed7fa11`. This supersedes the earlier PR #44 handover.

The current cross-platform previews are Linux
[`linux-preview-0.7.1b0.4`](../releases/linux-preview-0.7.1b0.4.md) and Windows
[`windows-preview-0.7.1b0.5`](../releases/windows-preview-0.7.1b0.5.md), both
built from `main` at `d7bbf50`. The earlier Windows b0.4 and Linux b0.3 assets
remain available as historical rollback artifacts and were not overwritten.
The release notes use the clean demo gallery and its
[capture procedure](../images/README.md).

The shared automated suite passed 274 tests, with 8 skips and 12 subtests.
macOS, Windows, and Ubuntu CI passed. Native macOS UI checks, distribution
audit, extracted startup, and color-PDF smoke checks passed separately. On
2026-10-20, the user reported that this current UI worked on a real Linux
machine and confirmed it on Windows. This is a general native success report,
not evidence for each OS/session, GPU/driver, scaling, package-smoke, or
checklist item; those detailed gates remain open where evidence is absent.
The macOS beta uses the existing ad-hoc signed `scripts/package_standalone.py`
workflow and is not Apple notarized.

## Final shared reader and bookshelf behavior

All behavior is in shared `src/mangacrisp_app/` code. No platform-specific
reader implementation is required.

- The reader has **no persistent bottom toolbar**. The settings sidebar is
  toggled with `P`; hiding it does not create another toolbar.
- A click in the center reading zone opens the translucent **Reading Controls**
  pane. It exposes previous/next spread, one-page back/forward, Original /
  Enhanced comparison, settings, fullscreen, layout, help, and (when enabled)
  bookmark and bookshelf actions. The pane is hidden until the center gesture.
- A click outside the pane in the page area dismisses it and consumes that
  click, so it cannot also turn the page. Blank left clicks inside the pane
  dismiss it; clicks on controls remain control clicks.
- `H` or `?` opens the modal shortcut-help pane. `Esc` closes that help pane;
  a matching outside press/release also closes it. The modal consumes the
  dismissal click, so the page or bookshelf underneath does not receive it.
- In the reader, `Esc` closes the controls pane first, then exits fullscreen,
  then returns to the bookshelf. Closing help with `Esc` or its backdrop does
  not exit fullscreen or change the page. The reading controls pane remains
  available while fullscreen is active, including for embedded readers.
- Reader shortcuts are accepted only for a visible reader with no modal or
  popup open and with the event target inside that reader. Arrow keys and
  editing remain with line edits, spin boxes, and combo boxes; `Esc` remains a
  reader-level escape from those fields. Space/Return on a focused button
  activates that button without turning a page. Ctrl/Command/Alt combinations
  are left to the focused control or the operating system.
- The existing bookshelf behavior remains shared: multi-selection, the
  Read/Remove context menu, one confirmation for batch removal, and source
  archive preservation. Failed managed-copy removal keeps the failed book
  registered and reports it while successful removals proceed.
- Fullscreen cursor auto-hide remains shared: it hides over the image after
  two seconds without input, returns on input or focus recovery, and stays
  visible over controls, overlays, popups, dialogs, drags, and inactive or
  closing windows.

The reader-controls UI checkpoints are:

| Checkpoint | Scope |
|---|---|
| `5320092` | First visible reader controls and translucent center pane |
| `8fd3c81` | On-demand controls, no persistent bottom toolbar, bookshelf refresh |
| `97dc06f` | Shortcut-help modal, `Esc`, backdrop dismissal, and focus handling |

## Correction and cache baseline

PR #53 (`78c2cc6`, with the implementation checkpoint at `1c1a8a6`) is part of
the same candidate and must stay with the reader controls.

- `models-pro` always invokes Real-CUGAN with accurate tile synchronization
  `-c 1`. Its parameter key includes `_syncgap1`, for example
  `scale3_noise3_tile0_models-pro_syncgap1`; old unsuffixed pro results are
  not treated as the same setting.
- Real-CUGAN writes to a temporary PNG inside the output directory. A result
  is published with an atomic replace only after a zero exit status, expected
  dimensions, PNG verification, and a second `load()` succeed. Failed,
  interrupted, corrupt, or wrongly sized output leaves an existing valid cache
  file untouched and does not expose a partial file as a cache hit.
- `CorrectionDiskCache` owns correction paths and session touch state. Normal
  image paths retain the legacy path/size/mtime-derived key. Lazy providers
  use `cache_source_identity(index)` without materializing a page. PDF page
  identity includes the PDF source key, DPI, and page index, so reopening or
  touching a rendered PNG does not churn the AI cache identity; an actual PDF
  source change intentionally produces a new identity.
- AI correction PNGs are bounded to **2 GiB** and **30 days** by the shared
  pruning utility. Active output files, their parent directories, and staging
  descendants are protected. Reader maintenance releases `processed_pages`
  references outside the protected navigation window while retaining completed
  disk results for bounded LRU/age cleanup, so ordinary backtracking does not
  force an immediate re-run.
- A cached output is touched at most once per reader session and never
  recreated by a cache lookup. Deleting a book removes its per-source
  correction folders; provider-backed deletion enumerates identities without
  rendering pages. PDF render PNGs use the same 2 GiB/30-day bounded-cache
  policy and the provider keeps a bounded recent-page working set.
- The visible display cache keeps the desired and fallback panes protected
  while asynchronous decodes complete. A late warm decode cannot evict a
  visible partner and cause a corrected-to-original flash.

## Bounded native acceptance checklist

Start from the current `main`, use redistributable demo material, and keep
platform packaging in its platform-specific files. Do not cross-build.

### Windows

Use `scripts/build_windows_app.py` and
`scripts/package_windows_portable.py` on Windows.

1. Open a demo book. Confirm center click opens controls, outside page click
   dismisses without turning a page, `H`/`?` opens help, and help `Esc` or
   backdrop dismissal leaves fullscreen and page position unchanged.
2. Confirm there is no persistent bottom toolbar; `P` only toggles the
   settings sidebar. Check arrows in a manual spin box/combo do not turn pages,
   while `Esc` closes the reader controls from those fields.
3. In fullscreen, confirm the controls pane remains usable and the cursor
   hides/restores as documented. Check both standalone and embedded reader
   paths if the package exposes both.
4. Use `models-pro` and inspect the command/result key for `_syncgap1`. Confirm
   a failed or malformed engine result does not replace an existing PNG, and
   that the corrected spread does not flash back to the original after
   prefetch completion.
5. Remove one enhanced book and a multi-selected group. Confirm one dialog,
   source archives retained, managed copies and per-page correction caches
   removed, and a locked managed copy remains registered while other removals
   succeed.
6. Run `uv run pytest -q` plus the Windows package smoke checks. Record the
   result and any GPU or clean-account limitation here before publishing a
   Windows candidate.

### Linux

Use `scripts/build_linux_app.py` on Ubuntu 24.04 or newer.

1. Repeat the reader, help, focus, fullscreen, `models-pro`, atomic-output,
   no-flash, and removal checks above.
2. Check cursor auto-hide separately on GNOME Wayland and X11. Check right
   click menu placement, Ctrl/Shift selection, and the portal/capture flow.
3. Confirm cache paths and cleanup under the Linux app-support directory and
   verify that active correction outputs and staging descendants survive prune.
4. Run `uv run pytest -q` including Linux capture tests. Record compositor,
   GPU, and scaling limitations rather than adding a Linux branch to the
   shared reader.

The Windows preview b0.4 and Linux preview b0.3 acceptance records remain in
their historical release documents. They are useful prior-platform evidence,
but do not replace the 2026-10-20 general report or close the detailed native
evidence gate for this final reader-controls candidate.

## Rollback and conflict boundaries

- Keep PR #53 / `1c1a8a6` (merged as `78c2cc6`) when investigating or rolling
  back reader UX. To remove only the reader-controls layer, revert the UI
  checkpoints in reverse order: `ed7fa11`, `97dc06f`, `8fd3c81`, then `5320092`. This
  changes source and UI only; it does not delete user books, settings, or
  caches.
- Rebase onto the current `main` before editing `viewer.py`, `bookshelf.py`,
  `page_provider.py`, `cache_utils.py`, or the correction modules. Preserve
  both the shared correction/cache fixes and platform packaging changes.
- Keep OS-specific capture, packaging, signing, and release work in
  `platform/` or `packaging/`. Do not copy a Windows or Linux workaround into
  the shared reader. See the [cross-platform workflow](cross-platform-workflow.md),
  [Windows handover](windows-handover.md), and [Linux handover](linux-handover.md).
- Update a platform download paragraph only after a native package containing
  this candidate passes its checklist and is actually published.
