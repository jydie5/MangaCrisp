# Reader and bookshelf UX handover (macOS-first)

[日本語](ux-maintenance-handover.ja.md)

The macOS side moved shared reader and bookshelf behavior forward in PR #44
(`core/reader-bookshelf-ux`, merged 2026-10-15). This document tells the
Windows and Linux maintainers what changed in shared code, what was verified
only on macOS, and what each platform needs to check before its next preview
build. Start every Windows or Linux task from the current `origin/main`.

## What changed in shared code

All changes live in `src/mangacrisp_app/` and are OS-independent. No
`platform/`, `packaging/`, or OS-specific script was touched.

| Area | Files | Behavior |
|---|---|---|
| Fullscreen cursor auto-hide | `cursor_autohide.py` (new), `viewer.py` | Cursor hides over the image area after 2 s without input while fullscreen; any mouse move, click, wheel or key shows it and restarts the timer. Never hides over the reading-info overlay, the next-book banner, during a drag, with a modal or popup open, when the window is inactive, when leaving fullscreen, or on close. |
| Bookshelf button on the reading-info overlay | `viewer.py`, `i18n.py` | Center click opens the overlay; its **Bookshelf** button leaves fullscreen, flushes the reading position and closes the reader. It is never treated as a page turn. The settings-panel button and `Esc` are unchanged. |
| Bookshelf multi-select and right-click | `bookshelf.py`, `i18n.py` | `QListWidget.ExtendedSelection` (Qt supplies Ctrl/Shift on Windows and Linux, Command/Shift on macOS). Right-click menu: *Read* / *Remove from bookshelf*. Right-clicking an unselected book selects only that book; inside the selection keeps it. |
| Shared delete flow | `bookshelf.py`, `viewer.py` | Delete/Backspace, the bottom button and the menu all call `BookshelfWindow.delete_books()`: one confirmation with the count and first three titles, then per-book removal of the managed copy, reading position, bookmarks, PDF render cache and per-page AI correction cache (`remove_enhancement_cache_for_sources`). Source archives are kept. Failures are reported together; successes stay removed. |
| Correction priority queue | `viewer.py` | The Real-CUGAN worker takes pages from `correction_queue` in `correction_priority` order (visible → forward → previous). Navigation while a worker runs calls `refresh_correction_queue()`, which re-prioritises and adds the newly visible pages. The in-flight page (`correction_in_flight`) is never re-queued. |
| Prefetch tuning | `viewer.py` | `DEFAULT_PREVIOUS_PREFETCH_COUNT` 4 → 6. Forward window is 12–24 normally, drops to `MIN_FORWARD_PREFETCH_COUNT` (6) when the median page-turn interval is ≥ `SLOW_READER_INTERVAL_SECONDS` (8 s), and the lead is multiplied by `CORRECTION_MISS_LEAD_FACTOR` (1.5) when the visible spread was shown uncorrected ≥ `CORRECTION_MISS_THRESHOLD` (2) times in the last `CORRECTION_MISS_WINDOW` (10) turns. |

New or changed tests: `test/test_cursor_autohide.py`, `test/test_bookshelf_delete.py`,
`test/test_prefetch_policy.py`, and additions to `test/test_viewer_navigation.py`.
The shared suite is `180 passed, 8 skipped` on macOS.

## Verified on macOS only

The following were checked by hand on an Apple Silicon Mac with
`dist/MangaCrisp.app` built by `scripts/build_macos_app.py --bundle-engine`
and the `demo/` Pepper&Carrot volumes:

- cursor hide after 2 s in fullscreen and restore on mouse, key, overlay hover,
  settings panel, drag, app switch and fullscreen exit
- overlay **Bookshelf** button from windowed and fullscreen reading
- Command/Shift multi-select, right-click on selected and unselected books,
  Delete-key and button removal, single confirmation, source ZIPs untouched
- corrected spread appears within about one engine run after a page turn, also
  after toggling `O` several times
- forward prefetch count falling to 6 while lingering, returning to 12+ when
  turning pages quickly

## What Windows must check

Use the portable build from `scripts/build_windows_app.py` and
`scripts/package_windows_portable.py` on Windows; do not cross-build.

1. **Cursor auto-hide**: `Qt.BlankCursor` on the image host. Confirm the cursor
   hides in fullscreen (`F`) and returns on move/key. Confirm it does not hide
   over the reading-info overlay, the next-book banner or the settings panel,
   and that it returns on `Alt+Tab` away and back.
2. **Selection modifiers**: Ctrl+click and Shift+click on the bookshelf grid.
   The help text already says "Command/Ctrl". No code change expected.
3. **Right-click menu**: `customContextMenuRequested` on the list. Confirm the
   menu appears at the pointer and that right-clicking an unselected cover
   selects only that cover.
4. **Removal**: delete two books at once, confirm one dialog, and confirm the
   managed folders under the library directory disappear while the source
   archives remain. Removing a book whose managed folder is open in Explorer
   should report that book as failed and keep the others removed.
5. **Correction cache removal**: after reading a book with enhancement, remove
   it and check `%LOCALAPPDATA%` / app-support `upscale/interactive/<key>/`
   no longer has that book's page folders.
6. **Prefetch**: open a book, turn pages at about one per second, then linger
   10 s and turn again; the settings panel status should show the prefetch
   count dropping to 6 and rising back.
7. Run the shared suite and the Windows-specific tests:
   `uv run pytest -q`.

Capture (`platform/capture_windows.py`), `Alt+C` / `Alt+U` and the taskbar
controller behavior are unaffected.

## Windows local candidate checkpoint (2026-10-15)

Windows caught up from `5e32e42` on `origin/main`. The candidate build identifier
is `0.7.1b0+win.ux.20261015`; the shared product version is still `0.7.1b0`.
The published Windows b0.4 download and release assets have not been changed.

- The Windows source suite passes: **183 passed, 9 skipped, 5 subtests passed**.
- Packaged GUI checks with an isolated Pepper&Carrot-only library cover color
  original/enhanced display, idle fullscreen cursor hiding, the overlay
  Bookshelf button, Shift range selection, right-click retaining two selected
  books, and the single removal dialog followed by cancellation.
- A real Windows open-file lock exposed an existing importer problem:
  `delete_managed_storage()` suppressed removal errors, allowing the database
  entry to disappear although managed files remained. The local
  `core/managed-removal-errors` fix propagates storage errors before deleting
  the database entry and tolerates already-missing storage. Its Windows
  regression verifies that the failed book remains registered, another book
  is removed successfully, and both source ZIPs remain unchanged.
- Failed recursive deletion can leave a partially removed managed copy. The
  source archive remains available for retry/re-import; deletion is not atomic.

Human acceptance is **pending**, not inferred from automated GUI checks. Use
[the Windows checklist](../testing/reader-bookshelf-human-check.windows.ja.md)
for Ctrl+click, app-switch cursor recovery, real deletion confirmation, and
longer reading/prefetch feel. No Windows/Linux source implementation of the
shared UX was duplicated, and capture adapters/hotkeys are unchanged.

The managed-removal fix is a shared `core/` change awaiting review. Other
platforms should take it through that branch/PR rather than copying a
Windows-specific workaround into their packaging.

## What Linux must check

Use `scripts/build_linux_app.py` on Ubuntu 24.04 or newer.

1. **Cursor auto-hide on Wayland and X11**: `Qt.BlankCursor` relies on the
   compositor honoring a blank cursor. Check GNOME Wayland and X11 separately.
   If a compositor keeps drawing the cursor, note it in this document rather
   than adding a platform branch in `viewer.py`; a Linux-only workaround
   belongs in `platform/linux.py`.
2. **Fullscreen exit restores the cursor** when leaving with `F`, `Esc`, or the
   overlay Bookshelf button, and when the window loses focus.
3. **Selection modifiers**: Ctrl+click and Shift+click on the bookshelf grid.
4. **Right-click menu** positioning under Wayland (popup placement is
   compositor-driven; the menu should still open at the pointer).
5. **Removal and cache cleanup** as for Windows, using
   `~/.local/share` / app-support `upscale/interactive/<key>/`.
6. **Prefetch** as for Windows.
7. Run `uv run pytest -q` including the Linux capture tests.

Capture (`platform/capture_linux.py`) and the GNOME portal flow are
unaffected.

## Shared files touched and how to avoid conflicts

| File | What changed | Conflict advice |
|---|---|---|
| `src/mangacrisp_app/viewer.py` | cursor timer and event tracking, overlay button, `return_to_bookshelf`, correction queue, prefetch constants and policy functions, `remove_enhancement_cache_for_sources` | Rebase onto `main` before touching `eventFilter`, `toggle_fullscreen`, `closeEvent`, `request_prefetch`, `start_prefetch`, `_process_pages_worker`, or `on_upscale_done`. The worker signature changed to `(settings, generation, parameter_key, is_prefetch)`. |
| `src/mangacrisp_app/bookshelf.py` | selection mode, context menu, `delete_books`, `selected_book_ids`, `remove_enhancement_cache`, helper functions above the class | `delete_selected_book` now delegates to `delete_books`; keep new removal paths going through it. |
| `src/mangacrisp_app/i18n.py` | new English strings for the overlay button, removal messages and bookshelf help | Append new strings; do not reorder the dictionary. |
| `test/test_viewer_navigation.py` | split into `ViewerWindowTestCase` base + test classes | Subclass `ViewerWindowTestCase` for new reader window tests. |

## Release notes for the next previews

When the Windows or Linux preview is next rebuilt from `main`, its release
document should list, in both languages:

- fullscreen cursor auto-hide
- Bookshelf button on the reading-info overlay
- bookshelf multi-select, right-click menu and batch removal
- visible-spread-first correction queue and the 6-page backward window
- the slower-reader prefetch reduction

The README already describes these as shared features; only the platform
download paragraphs need the "built from `main` at PR #44 or later" note.

## Open questions for the other platforms

- Whether `Qt.BlankCursor` is honored on every supported Linux compositor.
- Whether Windows needs the cursor restored explicitly when a UAC or system
  dialog steals focus (the `WindowDeactivate` path should cover it).
- Whether Intel/AMD GPUs need a different `CORRECTION_MISS_LEAD_FACTOR`; the
  constants are in `viewer.py` and covered by `test/test_prefetch_policy.py`.
