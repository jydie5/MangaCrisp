from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt

from mangacrisp_app.bookshelf import (
    READING_STATUS_FILTER_ALL,
    BookshelfWindow,
    bookshelf_grid_label,
    filter_books_for_discovery,
)
from mangacrisp_app.i18n import set_language
from mangacrisp_app.library import (
    Book,
    LibraryPaths,
    LibraryService,
    ReadingState,
    save_library_settings,
)


def _book(book_id: str, title: str, **updates) -> Book:
    return Book(
        id=book_id,
        title=title,
        source_uri=f"source://{book_id}",
        local_path=f"/library/{book_id}",
        source_kind="managed",
        file_kind="images",
        **updates,
    )


@pytest.fixture
def library(tmp_path):
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    service = LibraryService.open(paths)
    try:
        yield service
    finally:
        service.close()


def test_manual_status_update_resets_only_position_and_preserves_history(library):
    original = library.books.upsert(
        _book("one", "One", reading_status="reading", last_opened_at="2026-10-25T00:00:00Z")
    )
    library.reading_states.save(
        ReadingState(
            book_id=original.id,
            page_index=7,
            spread_mode="single",
            reading_direction="ltr",
            cover_single=False,
            correction_preset="高画質",
        )
    )
    bookmark = library.bookmarks.add(original.id, 7, "p.8")

    assert library.books.set_reading_status([original.id, original.id], "completed") == 1
    completed = library.books.get(original.id)
    state = library.reading_states.get(original.id)
    assert completed is not None and state is not None
    assert completed.reading_status == "completed"
    assert completed.last_opened_at == original.last_opened_at
    assert state.page_index == 7

    assert library.books.set_reading_status([original.id], "unread") == 1
    unread = library.books.get(original.id)
    reset_state = library.reading_states.get(original.id)
    assert unread is not None and reset_state is not None
    assert unread.reading_status == "unread"
    assert unread.last_opened_at == original.last_opened_at
    assert reset_state.page_index == 0
    assert (reset_state.spread_mode, reset_state.reading_direction, reset_state.cover_single) == (
        "single",
        "ltr",
        False,
    )
    assert reset_state.correction_preset == "高画質"
    assert [entry.id for entry in library.bookmarks.list_for_book(original.id)] == [bookmark.id]


def test_manual_unread_is_atomic_when_position_reset_fails(library):
    book = library.books.upsert(_book("one", "One", reading_status="reading"))
    library.reading_states.save(ReadingState(book_id=book.id, page_index=5))
    library.db.connection.execute(
        """
        CREATE TRIGGER reject_reading_position_reset
        BEFORE UPDATE OF page_index ON reading_state
        BEGIN
            SELECT RAISE(ABORT, 'position reset rejected');
        END
        """
    )
    library.db.connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="position reset rejected"):
        library.books.set_reading_status([book.id], "unread")

    unchanged_book = library.books.get(book.id)
    unchanged_state = library.reading_states.get(book.id)
    assert unchanged_book is not None and unchanged_state is not None
    assert unchanged_book.reading_status == "reading"
    assert unchanged_state.page_index == 5


def test_only_manual_unread_and_completed_statuses_are_accepted(library):
    with pytest.raises(ValueError, match="unsupported manual reading status"):
        library.books.set_reading_status(["one"], "reading")


def test_manual_status_update_batches_with_a_low_sqlite_variable_limit(library):
    if not hasattr(library.db.connection, "setlimit"):
        pytest.skip("sqlite build does not expose connection variable limits")
    books = [library.books.upsert(_book(f"book-{index}", f"Book {index}")) for index in range(24)]
    previous_limit = library.db.connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 8)
    try:
        assert library.books.set_reading_status([book.id for book in books], "completed") == len(books)
    finally:
        library.db.connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, previous_limit)
    assert {library.books.get(book.id).reading_status for book in books} == {"completed"}


def test_reading_saves_do_not_auto_complete_or_demote_completed(qapp, library):
    set_language("en")
    book = library.books.upsert(_book("one", "One"))
    shelf = BookshelfWindow(library)
    window = SimpleNamespace(
        index=99,
        page_layout_mode="single",
        reading_direction="rtl",
        cover_single=True,
        quality_preset_for_state="標準",
    )
    try:
        shelf.save_reading_state(book.id, window)
        reading = library.books.get(book.id)
        assert reading is not None and reading.reading_status == "reading"

        library.books.set_reading_status([book.id], "completed")
        shelf.save_reading_state(book.id, window)
        completed = library.books.get(book.id)
        assert completed is not None and completed.reading_status == "completed"
    finally:
        shelf.close()


def test_status_filter_and_bulk_action_only_apply_to_visible_selection(qapp, library):
    set_language("en")
    alpha = library.books.upsert(_book("alpha", "Alpha", reading_status="completed"))
    beta = library.books.upsert(_book("beta", "Beta", reading_status="reading"))
    library.books.upsert(_book("gamma", "Gamma", reading_status="unread"))
    shelf = BookshelfWindow(library)
    try:
        items = {
            shelf.list_widget.item(row).data(Qt.UserRole): shelf.list_widget.item(row)
            for row in range(shelf.list_widget.count())
        }
        items[alpha.id].setSelected(True)
        items[beta.id].setSelected(True)
        shelf.list_widget.setCurrentItem(items[alpha.id], QItemSelectionModel.NoUpdate)
        shelf.reading_status_combo.setCurrentIndex(shelf.reading_status_combo.findData("completed"))
        qapp.processEvents()
        assert shelf.selected_book_ids() == [alpha.id]

        shelf.set_selected_reading_status("unread")
        assert library.books.get(alpha.id).reading_status == "unread"
        assert library.books.get(beta.id).reading_status == "reading"

        shelf.reading_status_combo.setCurrentIndex(
            shelf.reading_status_combo.findData(READING_STATUS_FILTER_ALL)
        )
        qapp.processEvents()
        assert alpha.id in shelf.selected_book_ids()
    finally:
        shelf.close()


def test_status_filter_composes_with_search_recent_and_sort():
    snapshot = [
        (_book("one", "Alpha", reading_status="completed", last_opened_at="2026-10-25T00:00:00Z"), None),
        (_book("two", "Alpha sequel", reading_status="completed", last_opened_at=None), None),
        (_book("three", "Beta", reading_status="reading", last_opened_at="2026-10-26T00:00:00Z"), None),
    ]
    entries = filter_books_for_discovery(
        snapshot,
        query="alpha",
        sort_key="last_opened",
        recent_only=True,
        reading_status="completed",
    )
    assert [book.id for book, _state in entries] == ["one"]


def test_status_controls_and_card_label_fit_the_minimum_bookshelf_width(qapp, library):
    set_language("en")
    book = library.books.upsert(_book("one", "A deliberately long volume title", reading_status="completed"))
    state = ReadingState(book_id=book.id, page_index=12)
    shelf = BookshelfWindow(library)
    try:
        shelf.resize(shelf.minimumSize())
        shelf.show()
        qapp.processEvents()
        label = bookshelf_grid_label(book, state)
        assert label.splitlines()[-1] == "Completed"
        assert shelf.list_widget.gridSize().height() == 292
        assert shelf.reading_status_combo.width() > 0
        assert shelf.reading_status_button.width() > 0
        assert shelf.reading_status_button.geometry().right() <= shelf.contentsRect().right()
    finally:
        shelf.close()
