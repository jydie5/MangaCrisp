from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox, QWidget

from mangacrisp_app import reading_backup_dialogs as dialogs
from mangacrisp_app.i18n import set_language
from mangacrisp_app.library import (
    Book,
    LibraryPaths,
    LibraryService,
    ReadingState,
    save_library_settings,
)
from mangacrisp_app.reading_backup import export_reading_backup


@pytest.fixture
def saved_records(tmp_path):
    paths = LibraryPaths.for_base_dir(tmp_path / "library")
    save_library_settings(paths, library_dir_confirmed=True)
    library = LibraryService.open(paths)
    book = library.books.upsert(Book(
        id="synthetic-book", title="Example", source_uri="synthetic", local_path="unused",
        source_kind="managed", file_kind="images", page_count=10,
        reading_status="completed",
    ))
    library.reading_states.save(ReadingState(book.id, 3))
    backup = tmp_path / "records.json"
    export_reading_backup(library, backup)
    library.reading_states.save(ReadingState(book.id, 8))
    library.books.upsert(book.with_updates(reading_status="reading"))
    yield library, book, backup
    library.close()


def test_restore_cancel_preserves_current_records(qapp, monkeypatch, saved_records):
    library, book, backup = saved_records
    parent = QWidget()
    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", lambda *args: (str(backup), ""))
    messages = []

    def cancel(message):
        messages.append(message)
        assert message.defaultButton() == message.button(QMessageBox.Cancel)
        return QMessageBox.Cancel

    monkeypatch.setattr(QMessageBox, "exec", cancel)
    assert dialogs.restore_records(parent, library) is False
    assert len(messages) == 1
    assert library.reading_states.get(book.id).page_index == 8
    assert library.books.get(book.id).reading_status == "reading"
    parent.close()


def test_confirmed_restore_applies_saved_records(qapp, monkeypatch, saved_records):
    library, book, backup = saved_records
    set_language("en")
    parent = QWidget()
    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", lambda *args: (str(backup), ""))
    texts = []

    def confirm(message):
        texts.append(message.text())
        for button in message.buttons():
            if message.buttonRole(button) == QMessageBox.AcceptRole:
                button.click()
                return QMessageBox.Ok
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "exec", confirm)
    assert dialogs.restore_records(parent, library) is True
    assert library.reading_states.get(book.id).page_index == 3
    assert library.books.get(book.id).reading_status == "completed"
    assert len(texts) == 2
    parent.close()


def test_invalid_file_reports_error_without_mutation(qapp, monkeypatch, saved_records, tmp_path):
    library, book, _backup = saved_records
    invalid = tmp_path / "broken.json"
    invalid.write_text("{broken", encoding="utf-8")
    parent = QWidget()
    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", lambda *args: (str(invalid), ""))
    seen = []
    monkeypatch.setattr(QMessageBox, "exec", lambda message: seen.append(message.icon()))
    assert dialogs.restore_records(parent, library) is False
    assert seen == [QMessageBox.Warning]
    assert library.reading_states.get(book.id).page_index == 8
    assert library.books.get(book.id).reading_status == "reading"
    parent.close()


def test_file_picker_cancel_does_not_export_or_restore(qapp, monkeypatch, saved_records):
    library, _book, _backup = saved_records
    parent = QWidget()
    monkeypatch.setattr(dialogs.QFileDialog, "getOpenFileName", lambda *args: ("", ""))
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    monkeypatch.setattr(QMessageBox, "exec", lambda _: pytest.fail("unexpected dialog"))
    assert dialogs.restore_records(parent, library) is False
    assert dialogs.export_records(parent, library) is False
    parent.close()


def test_export_writes_selected_destination(qapp, monkeypatch, saved_records, tmp_path):
    library, _book, _backup = saved_records
    destination = tmp_path / "new-records.json"
    parent = QWidget()
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", lambda *args: (str(destination), ""))
    monkeypatch.setattr(QMessageBox, "exec", lambda _: QMessageBox.Ok)
    assert dialogs.export_records(parent, library) is True
    assert dialogs.load_reading_backup(destination).books
    parent.close()


def test_bookshelf_blocks_backup_actions_during_import_or_reading(qapp, monkeypatch, saved_records):
    from mangacrisp_app.bookshelf import BookshelfWindow

    library, _book, _backup = saved_records
    shelf = BookshelfWindow(library)
    calls = []
    monkeypatch.setattr(dialogs, "export_records", lambda *args: calls.append("export"))
    monkeypatch.setattr(dialogs, "restore_records", lambda *args: calls.append("restore"))
    try:
        for reading, importing in ((False, True), (True, False)):
            shelf.register_running = importing
            shelf.active_reader = object() if reading else None
            shelf.update_action_states()
            assert not shelf.export_records_action.isEnabled()
            assert not shelf.restore_records_action.isEnabled()
            shelf.export_reading_records()
            shelf.restore_reading_records()
        assert calls == []
        shelf.active_reader = None
        shelf.register_running = False
        shelf.update_action_states()
        assert shelf.export_records_action.isEnabled()
        assert shelf.restore_records_action.isEnabled()
    finally:
        shelf.active_reader = None
        shelf.close()
