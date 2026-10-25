from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication, QMainWindow

from mangacrisp_app.bookmark_dialog import BookmarkDialog, BookmarkEditorDialog
from mangacrisp_app.bookshelf import BookshelfWindow
from mangacrisp_app.i18n import set_language
from mangacrisp_app.library import (
    Book,
    Bookmark,
    LibraryPaths,
    LibraryService,
    save_library_settings,
)
from mangacrisp_app.reading_backup import (
    export_reading_backup,
    preview_reading_restore,
    restore_reading_backup,
)


def _book(book_id: str, title: str) -> Book:
    return Book(
        id=book_id,
        title=title,
        source_uri=f"source://{book_id}",
        local_path=f"/library/{book_id}",
        source_kind="managed",
        file_kind="images",
        page_count=8,
    )


@pytest.fixture
def library(tmp_path: Path):
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    service = LibraryService.open(paths)
    try:
        yield service
    finally:
        service.close()


@pytest.fixture
def parent(qapp):
    window = QMainWindow()
    window.resize(900, 620)
    window.show()
    qapp.processEvents()
    try:
        yield window
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()


def test_repository_update_enforces_ownership_and_preserves_identity(library):
    first = library.books.upsert(_book("first", "First"))
    second = library.books.upsert(_book("second", "Second"))
    bookmark = library.bookmarks.add(first.id, 3, "old label", note="old note")

    updated = library.bookmarks.update(first.id, bookmark.id, "  new\r\nlabel  ", "new note")
    assert updated is not None
    assert (updated.id, updated.book_id, updated.page_index, updated.created_at) == (
        bookmark.id,
        first.id,
        3,
        bookmark.created_at,
    )
    assert (updated.label, updated.note) == ("new label", "new note")
    assert library.bookmarks.update(second.id, bookmark.id, "wrong owner", None) is None
    unchanged = library.bookmarks.list_for_book(first.id)[0]
    assert (unchanged.label, unchanged.note) == ("new label", "new note")


def test_repository_rejects_blank_labels_and_turns_blank_note_into_none(library):
    book = library.books.upsert(_book("one", "One"))
    bookmark = library.bookmarks.add(book.id, 1, "keep", note="old")
    with pytest.raises(ValueError, match="label cannot be empty"):
        library.bookmarks.update(book.id, bookmark.id, " \n\r ", "new")
    updated = library.bookmarks.update(book.id, bookmark.id, "kept", "  \n  ")
    assert updated is not None and updated.note is None


def test_repository_update_rolls_back_when_the_database_rejects_the_edit(library):
    book = library.books.upsert(_book("one", "One"))
    bookmark = library.bookmarks.add(book.id, 1, "before", note="before note")
    library.db.connection.executescript(
        """
        CREATE TRIGGER reject_bookmark_edit
        BEFORE UPDATE ON bookmarks
        WHEN NEW.label = 'reject'
        BEGIN
            SELECT RAISE(ABORT, 'synthetic bookmark update failure');
        END;
        """
    )
    library.db.connection.commit()
    with pytest.raises(sqlite3.IntegrityError, match="synthetic bookmark update failure"):
        library.bookmarks.update(book.id, bookmark.id, "reject", "new note")
    unchanged = library.bookmarks.list_for_book(book.id)[0]
    assert (unchanged.label, unchanged.note) == ("before", "before note")


def test_editor_cancel_never_calls_save_callback(parent, qapp):
    bookmark = Bookmark("bookmark", "book", 1, "label", "note")
    calls: list[tuple[str, str, str | None]] = []
    editor = BookmarkEditorDialog(parent, bookmark, lambda *args: calls.append(args) or bookmark)
    editor.show()
    qapp.processEvents()
    try:
        editor.label_edit.setText("changed")
        editor.cancel_button.click()
        qapp.processEvents()
        assert calls == []
        assert editor.result() == editor.DialogCode.Rejected
    finally:
        editor.close()
        editor.deleteLater()


def test_editor_keeps_plain_text_input_open_when_save_fails(parent, qapp):
    bookmark = Bookmark("bookmark", "book", 1, "label", None)
    editor = BookmarkEditorDialog(parent, bookmark, lambda *_args: None)
    editor.show()
    qapp.processEvents()
    try:
        editor.label_edit.setText("<b>literal</b>")
        editor.note_edit.setPlainText("line one\n<b>literal note</b>")
        editor.save_button.click()
        qapp.processEvents()
        assert editor.isVisible()
        assert editor.label_edit.text() == "<b>literal</b>"
        assert editor.note_edit.toPlainText() == "line one\n<b>literal note</b>"
        assert editor.updated_bookmark is None
    finally:
        editor.close()
        editor.deleteLater()


def test_dialog_edit_replaces_only_successful_snapshot_and_shows_note_preview(parent, qapp):
    bookmark = Bookmark("bookmark", "book", 9, "<b>literal</b>", "note one\nnote two")
    dialog = BookmarkDialog(
        parent,
        [bookmark],
        3,
        edit_callback=lambda bookmark_id, label, note: replace(
            bookmark, id=bookmark_id, label=label, note=note
        ),
    )
    dialog.show()
    qapp.processEvents()
    try:
        assert dialog.edit_button.isEnabled()  # Invalid pages are editable even though they cannot navigate.
        assert "<b>literal</b>" in dialog.list_widget.item(0).text()
        assert "note one note two" in dialog.list_widget.item(0).text()
        tooltip = QTextDocument()
        tooltip.setHtml(dialog.list_widget.item(0).toolTip())
        assert "note one\nnote two" in tooltip.toPlainText()
        assert "<b>literal</b>" in tooltip.toPlainText()

        def save_editor() -> None:
            editor = QApplication.activeModalWidget()
            assert isinstance(editor, BookmarkEditorDialog)
            editor.label_edit.setText("edited")
            editor.note_edit.setPlainText("edited note")
            editor.save_button.click()

        QTimer.singleShot(0, save_editor)
        dialog._edit_selected()
        assert "edited" in dialog.list_widget.item(0).text()
        assert "edited note" in dialog.list_widget.item(0).text()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_bookshelf_edit_rejects_missing_records_and_other_book_ownership(qapp, library):
    first = library.books.upsert(_book("first", "First"))
    second = library.books.upsert(_book("second", "Second"))
    bookmark = library.bookmarks.add(first.id, 1, "first")
    shelf = BookshelfWindow(library)
    try:
        assert shelf.update_bookmark(second.id, bookmark.id, "wrong", None) is None
        assert shelf.update_bookmark("missing", bookmark.id, "missing", None) is None
        updated = shelf.update_bookmark(first.id, bookmark.id, "right", "note")
        assert updated is not None and (updated.label, updated.note) == ("right", "note")
    finally:
        shelf.close()


def test_backup_restores_edited_label_and_note_after_the_target_bookmark_is_removed(tmp_path: Path, library):
    book = library.books.upsert(_book("one", "One"))
    bookmark = library.bookmarks.add(book.id, 2, "original")
    updated = library.bookmarks.update(book.id, bookmark.id, "edited label", "edited note")
    assert updated is not None
    backup_path = tmp_path / "bookmark.mangacrisp.json"
    document = export_reading_backup(library, backup_path)
    assert library.bookmarks.delete(bookmark.id)

    plan = preview_reading_restore(library, document)
    restore_reading_backup(library, plan)
    restored = library.bookmarks.list_for_book(book.id)
    assert [(item.label, item.note) for item in restored] == [("edited label", "edited note")]

    later = library.bookmarks.update(book.id, bookmark.id, "later label", "later note")
    assert later is not None
    restore_reading_backup(library, preview_reading_restore(library, document))
    assert [(item.label, item.note) for item in library.bookmarks.list_for_book(book.id)] == [
        ("later label", "later note")
    ]


@pytest.mark.parametrize("language,expected", [
    ("ja", "しおりのラベルを入力してください。"),
    ("en", "Enter a bookmark label."),
])
def test_editor_validation_uses_the_selected_language(parent, language, expected):
    set_language(language)
    bookmark = Bookmark("bookmark", "book", 1, "label", None)
    editor = BookmarkEditorDialog(parent, bookmark, lambda *_: pytest.fail("invalid input saved"))
    try:
        editor.label_edit.setText("   ")
        editor.save_button.click()
        assert expected in editor.status_label.text()
        assert editor.updated_bookmark is None
    finally:
        editor.close()
        editor.deleteLater()


def test_edit_preserves_selection_for_subsequent_jump(parent, monkeypatch):
    bookmarks = [Bookmark(str(i), "book", i, f"p.{i+1}") for i in range(3)]
    dialog = BookmarkDialog(parent, bookmarks, 3, edit_callback=lambda *_: None)
    try:
        dialog.list_widget.setCurrentRow(1)

        def accepted_edit(editor):
            editor.updated_bookmark = replace(editor.bookmark, label="changed")
            return editor.DialogCode.Accepted

        monkeypatch.setattr(BookmarkEditorDialog, "exec", accepted_edit)
        dialog._edit_selected()
        assert dialog.list_widget.currentItem().data(Qt.UserRole) == "1"
        dialog._accept_selected()
        assert dialog.selected_page_index == 1
    finally:
        dialog.close()
        dialog.deleteLater()
