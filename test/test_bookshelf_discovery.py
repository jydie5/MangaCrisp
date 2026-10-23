from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from mangacrisp_app.bookshelf import (
    BOOK_SORT_CREATED,
    BOOK_SORT_LAST_OPENED,
    BOOK_SORT_TITLE,
    BookshelfWindow,
    filter_books_for_discovery,
)
from mangacrisp_app.i18n import set_language
from mangacrisp_app.library import (
    Book,
    LibraryPaths,
    LibraryService,
    save_library_settings,
)


def _book(book_id: str, title: str, *, last_opened_at: str | None = None, created_at: str | None = None) -> Book:
    return Book(
        id=book_id,
        title=title,
        source_uri=f"source://{book_id}",
        local_path=f"/library/{book_id}",
        source_kind="managed",
        file_kind="images",
        last_opened_at=last_opened_at,
        created_at=created_at,
    )


def _titles(entries) -> list[str]:
    return [book.title for book, _state in entries]


def test_discovery_filter_uses_natural_title_and_cached_metadata() -> None:
    snapshot = [
        (_book("10", "Series 10", created_at="2026-01-02T00:00:00Z"), None),
        (_book("2", "Series 2", last_opened_at="2026-01-03T00:00:00Z", created_at="2026-01-01T00:00:00Z"), None),
        (_book("1", "Other", last_opened_at="2026-01-04T00:00:00Z", created_at="2026-01-03T00:00:00Z"), None),
        (_book("11", "シリーズ 10", last_opened_at="2026-01-05T00:00:00Z"), None),
        (_book("12", "シリーズ 2", last_opened_at="2026-01-05T00:00:00Z"), None),
    ]

    assert _titles(filter_books_for_discovery(snapshot, query="series", sort_key=BOOK_SORT_TITLE)) == [
        "Series 2",
        "Series 10",
    ]
    assert _titles(filter_books_for_discovery(snapshot, query="SERIES", sort_key=BOOK_SORT_TITLE)) == [
        "Series 2",
        "Series 10",
    ]
    assert _titles(filter_books_for_discovery(snapshot, sort_key=BOOK_SORT_LAST_OPENED)) == [
        "シリーズ 2",
        "シリーズ 10",
        "Other",
        "Series 2",
        "Series 10",
    ]
    assert _titles(filter_books_for_discovery(snapshot, sort_key=BOOK_SORT_CREATED)) == [
        "Other",
        "Series 10",
        "Series 2",
        "シリーズ 2",
        "シリーズ 10",
    ]
    assert _titles(filter_books_for_discovery(snapshot, sort_key=BOOK_SORT_LAST_OPENED, recent_only=True)) == [
        "シリーズ 2",
        "シリーズ 10",
        "Other",
        "Series 2",
    ]
    assert _titles(filter_books_for_discovery(snapshot, query="シリーズ", sort_key=BOOK_SORT_LAST_OPENED)) == [
        "シリーズ 2",
        "シリーズ 10",
    ]


def _bookshelf(tmp_path: Path, titles: tuple[str, ...], language: str = "en") -> BookshelfWindow:
    set_language(language)
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    library = LibraryService.open(paths)
    for title in titles:
        folder = tmp_path / title
        folder.mkdir()
        Image.new("RGB", (80, 120), (60, 90, 130)).save(folder / "001.png")
        registered = library.register_local_book(folder)
        book = library.books.get(registered.id)
        assert book is not None
        library.books.upsert(book.with_updates(title=title))
    return BookshelfWindow(library)


def _visible_ids(window: BookshelfWindow) -> list[str]:
    return [window.list_widget.item(row).data(Qt.UserRole) for row in range(window.list_widget.count())]


def _wait_for_discovery(qapp) -> None:
    QTest.qWait(220)
    qapp.processEvents()


def test_search_restores_hidden_selection_and_current_position(qapp, tmp_path: Path) -> None:
    window = _bookshelf(tmp_path, ("Alpha", "Beta", "Gamma"))
    try:
        first_item = window.list_widget.item(0)
        second_item = window.list_widget.item(1)
        assert first_item is not None and second_item is not None
        first_id = first_item.data(Qt.UserRole)
        second_id = second_item.data(Qt.UserRole)
        first_item.setSelected(True)
        second_item.setSelected(True)
        window.list_widget.setCurrentItem(first_item, QItemSelectionModel.NoUpdate)
        window.search_edit.setText("Beta")
        _wait_for_discovery(qapp)
        assert window.list_widget.count() == 1
        assert window.selected_book_ids() == [second_id]

        window.search_edit.clear()
        _wait_for_discovery(qapp)
        assert window.list_widget.count() == 3
        assert window.selected_book_ids() == [first_id, second_id]
        assert window.list_widget.currentItem().data(Qt.UserRole) == first_id
    finally:
        window.close()


def test_filtered_delete_only_uses_visible_selection(qapp, tmp_path: Path) -> None:
    window = _bookshelf(tmp_path, ("Alpha", "Beta", "Gamma"))
    try:
        window.list_widget.item(0).setSelected(True)
        window.list_widget.item(1).setSelected(True)
        hidden_id = window.list_widget.item(0).data(Qt.UserRole)
        visible_id = window.list_widget.item(1).data(Qt.UserRole)
        window.search_edit.setText("Beta")
        _wait_for_discovery(qapp)
        assert _visible_ids(window) == [visible_id]
        assert window.selected_book_ids() == [visible_id]

        with patch.object(QMessageBox, "exec", return_value=QMessageBox.Yes):
            window.delete_selected_book()

        remaining = {book.id for book in window.library.books.list_books()}
        assert visible_id not in remaining
        assert hidden_id in remaining
    finally:
        window.close()


def test_recent_view_switches_to_last_opened_and_search_does_not_reload(qapp, tmp_path: Path) -> None:
    window = _bookshelf(tmp_path, ("Alpha", "Beta", "Gamma"))
    try:
        books = window.library.books.list_books()
        by_title = {book.title: book for book in books}
        for title, last_opened in (("Alpha", "2026-01-01T00:00:00Z"), ("Beta", None), ("Gamma", "2026-01-03T00:00:00Z")):
            window.library.books.upsert(by_title[title].with_updates(last_opened_at=last_opened))
        window.reload_books()
        assert _titles(filter_books_for_discovery(window._book_snapshot, sort_key=BOOK_SORT_LAST_OPENED)) == [
            "Gamma",
            "Alpha",
            "Beta",
        ]

        list_books = window.library.books.list_books
        reading_state_get = window.library.reading_states.get
        with patch.object(window.library.books, "list_books", wraps=list_books) as list_books_mock, patch.object(
            window.library.reading_states, "get", wraps=reading_state_get
        ) as reading_state_mock:
            window.recent_button.click()
            assert window.sort_combo.currentData() == BOOK_SORT_LAST_OPENED
            assert window.sort_combo.isEnabled() is False
            assert _visible_ids(window) == [by_title["Gamma"].id, by_title["Alpha"].id]
            assert list_books_mock.call_count == 0
            assert reading_state_mock.call_count == 0
            window.search_edit.setText("Alpha")
            _wait_for_discovery(qapp)
            assert _visible_ids(window) == [by_title["Alpha"].id]
            assert list_books_mock.call_count == 0
            assert reading_state_mock.call_count == 0
        window.recent_button.click()
        assert window.sort_combo.isEnabled() is True
    finally:
        window.close()


def test_discovery_controls_are_translated_in_both_languages(qapp, tmp_path: Path) -> None:
    expected = {
        "en": ("Search titles", "Title", "Recently read"),
        "ja": ("タイトルを検索", "タイトル順", "最近読んだ本"),
    }
    for language, (placeholder, title_sort, recent_label) in expected.items():
        window = _bookshelf(tmp_path / language, ("Sample",), language=language)
        try:
            assert window.search_edit.placeholderText() == placeholder
            assert window.sort_combo.itemText(0) == title_sort
            assert window.recent_button.text() == recent_label
        finally:
            window.close()
