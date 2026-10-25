from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from PySide6.QtWidgets import QApplication

import mangacrisp_app.viewer as viewer_module
from mangacrisp_app.bookmark_dialog import BookmarkDialog, BookmarkEditorDialog
from mangacrisp_app.bookshelf import BookshelfWindow
from mangacrisp_app.i18n import set_language
from mangacrisp_app.library import (
    LibraryPaths,
    LibraryService,
    ReadingState,
    save_library_settings,
)
from mangacrisp_app.page_overview import PageOverviewDialog
from mangacrisp_app.shortcut_help import ShortcutHelpDialog
from mangacrisp_app.viewer import SpreadWindow, viewer_shortcuts_text


def process_events(app: QApplication, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)


def capture(demo_dir: Path, output_dir: Path, language: str = "en") -> None:
    archives = sorted(demo_dir.glob("*.zip"))
    if not archives:
        raise RuntimeError(f"no demo ZIP files found in {demo_dir}")

    set_language(language)
    app = QApplication.instance() or QApplication([])
    output_dir.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="mangacrisp-readme-") as temporary_directory:
        # Resolve macOS's /var -> /private/var alias before importing. Cover
        # paths must follow the final import directory after its atomic rename.
        paths = LibraryPaths.for_base_dir(Path(temporary_directory).resolve())
        save_library_settings(paths, library_dir_confirmed=True)
        library = LibraryService.open(paths)
        try:
            for archive in archives:
                for book in library.register_local_books(archive):
                    library.importer.import_book(book)

            books = sorted(library.books.list_books(), key=lambda item: item.title)
            if len(books) < 3:
                raise RuntimeError("gallery requires three redistributable demo books")
            library.books.record_reading_progress(books[1].id)
            library.reading_states.save(ReadingState(books[1].id, 1))
            library.books.record_reading_progress(books[2].id)
            library.books.set_reading_status([books[2].id], "completed")
            library.reading_states.save(ReadingState(books[2].id, 1))
            demo_bookmark = library.bookmarks.add(
                books[2].id,
                1,
                "お気に入りの場面" if language == "ja" else "A favorite scene",
                note=(
                    "あとで読み返す場面。\n色と構図を見比べる。"
                    if language == "ja"
                    else "A scene to revisit.\nCompare the colors and composition."
                ),
            )

            bookshelf = BookshelfWindow(library)
            bookshelf.resize(1400, 900)
            bookshelf.library_location_label.setText(
                "デモ本棚: Pepper&Carrot (CC BY 4.0)    3冊"
                if language == "ja"
                else "Demo library: Pepper&Carrot (CC BY 4.0)    3 books"
            )
            bookshelf.show()
            process_events(app, 0.8)
            bookshelf.list_widget.setCurrentRow(0)
            process_events(app, 0.2)
            if not bookshelf.grab().save(str(output_dir / "bookshelf.png")):
                raise RuntimeError("failed to save bookshelf screenshot")
            bookshelf.hide()

            books = sorted(library.books.list_books(), key=lambda item: item.title)
            selected = books[-1]
            pages = sorted(
                path
                for path in Path(selected.local_path).glob("*")
                if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            )
            # Keep this gallery run completely independent from the developer's
            # normal correction and display caches.  SpreadWindow looks up
            # these module globals when it creates its disk caches.
            viewer_module.DEFAULT_UPSCALE_DIR = paths.cache_dir / "upscale"
            viewer_module.DISPLAY_CACHE_DIR = viewer_module.DEFAULT_UPSCALE_DIR / "display_cache"
            reader = SpreadWindow(
                pages=pages,
                title=selected.title,
                reading_direction="ltr",
                spread_order="ltr",
                cover_single=False,
                auto_prefetch=False,
                bookmark_callback=lambda page_index: bookshelf.add_bookmark(selected.id, page_index),
                bookmarks_provider=lambda: library.bookmarks.list_for_book(selected.id),
                bookmark_delete_callback=lambda bookmark_id: bookshelf.delete_bookmark(
                    selected.id, bookmark_id
                ),
                bookmark_edit_callback=lambda bookmark_id, label, note: bookshelf.update_bookmark(
                    selected.id, bookmark_id, label, note
                ),
                settings_path=paths.settings_path,
            )
            reader.index = min(1, max(0, len(pages) - 2))
            reader.resize(1600, 1000)
            reader.show()
            reader.render_spread()
            process_events(app, 1.5)
            if not reader.grab().save(str(output_dir / "reader.png")):
                raise RuntimeError("failed to save reader screenshot")
            reader.toggle_controls()
            process_events(app, 0.3)
            reader.toggle_reading_info()
            process_events(app, 0.4)
            if not reader.grab().save(str(output_dir / "reader-controls.png")):
                raise RuntimeError("failed to save reading-controls screenshot")
            reader.dismiss_reading_overlay()
            help_dialog = ShortcutHelpDialog(reader, viewer_shortcuts_text("ltr"))
            help_dialog.show()
            process_events(app, 0.3)
            if not help_dialog.card.grab().save(str(output_dir / "shortcut-help.png")):
                raise RuntimeError("failed to save shortcut-help screenshot")
            help_dialog.close()

            bookmarks = BookmarkDialog(
                reader,
                library.bookmarks.list_for_book(selected.id),
                len(pages),
                delete_callback=reader.bookmark_delete_callback,
                edit_callback=reader.bookmark_edit_callback,
            )
            bookmarks.show()
            process_events(app, 0.3)
            if not bookmarks.card.grab().save(str(output_dir / "bookmarks.png")):
                raise RuntimeError("failed to save bookmark-list screenshot")
            bookmarks.close()
            editor = BookmarkEditorDialog(reader, demo_bookmark, reader.bookmark_edit_callback)
            editor.show()
            process_events(app, 0.2)
            if not editor.grab().save(str(output_dir / "bookmark-edit.png")):
                raise RuntimeError("failed to save bookmark-editor screenshot")
            editor.close()

            overview = PageOverviewDialog(reader, pages, reader.index)
            overview.show()
            # Let the dialog position its initial tile and schedule the visible
            # window before waiting for the single thumbnail worker.  Waiting
            # for the worker makes the gallery prove that the grid contains
            # actual page images rather than the loading placeholders.
            process_events(app, 0.25)
            overview.request_timer.stop()
            overview.request_visible_thumbnails()
            requested_indexes = set(overview._requested_indexes)
            if not overview.controller.pool.waitForDone(10_000):
                raise RuntimeError("page overview thumbnails did not finish")
            process_events(app, 0.3)
            loaded_indexes = {
                index for index, tile in enumerate(overview.tiles) if not tile.icon().isNull()
            }
            missing_indexes = requested_indexes - loaded_indexes
            if missing_indexes:
                raise RuntimeError(
                    "page overview thumbnails did not load: "
                    + ", ".join(str(index + 1) for index in sorted(missing_indexes))
                )
            if not overview.card.grab().save(str(output_dir / "page-overview.png")):
                raise RuntimeError("failed to save page-overview screenshot")
            overview.close()
            reader.close()
            bookshelf.close()
            process_events(app, 0.2)
        finally:
            library.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture README screenshots with free demo books."
    )
    parser.add_argument("--demo-dir", type=Path, default=REPOSITORY_ROOT / "demo")
    parser.add_argument(
        "--output-dir", type=Path, default=REPOSITORY_ROOT / "docs" / "images"
    )
    parser.add_argument("--language", choices=("en", "ja"), default="en")
    args = parser.parse_args()
    capture(args.demo_dir.resolve(), args.output_dir.resolve(), args.language)


if __name__ == "__main__":
    main()
