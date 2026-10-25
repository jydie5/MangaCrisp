from __future__ import annotations

import copy
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from mangacrisp_app.library import (
    LibraryPaths,
    LibraryService,
    ReadingState,
    save_library_settings,
)
from mangacrisp_app.reading_backup import (
    MAX_BACKUP_BYTES,
    ReadingBackupStalePlan,
    ReadingBackupValidationError,
    ReadingRestoreResult,
    export_reading_backup,
    load_reading_backup,
    preview_reading_restore,
    restore_reading_backup,
)


def _library(tmp_path: Path, names: tuple[str, ...] = ("Alpha", "Beta")):
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    library = LibraryService.open(paths)
    books = []
    for name in names:
        source = tmp_path / f"source-{name}"
        source.mkdir()
        for page in range(4):
            Image.new("RGB", (80, 120), (30 + page, 80, 140)).save(source / f"{page:04d}.png")
        books.append(library.register_local_book(source))
    return paths, library, books


def _seed_reading_metadata(library: LibraryService, book_id: str, *, bookmark_label: str = "p.2") -> None:
    library.reading_states.save(
        ReadingState(
            book_id=book_id,
            page_index=2,
            spread_mode="single",
            reading_direction="ltr",
            cover_single=False,
            fit_mode="page",
            zoom=1.25,
            pan_x=12.0,
            pan_y=-4.0,
            correction_preset="自然",
        )
    )
    library.bookmarks.add(book_id, 1, label=bookmark_label, note="keep this")


def _clear_reading_metadata(library: LibraryService, book_ids: list[str]) -> None:
    connection = library.db.connection
    for book_id in book_ids:
        connection.execute("DELETE FROM reading_state WHERE book_id = ?", (book_id,))
        connection.execute("DELETE FROM bookmarks WHERE book_id = ?", (book_id,))
        connection.execute(
            "UPDATE books SET reading_status = 'unread', last_opened_at = NULL WHERE id = ?",
            (book_id,),
        )
    connection.commit()


def _result_for_plan(plan) -> ReadingRestoreResult:
    return ReadingRestoreResult(
        matched_books=plan.matched_books,
        missing_books=plan.missing_books,
        incompatible_books=plan.incompatible_books,
        bookmarks_added=plan.bookmarks_added,
        bookmarks_skipped=plan.bookmarks_skipped,
        bookmark_conflicts=plan.bookmark_conflicts,
        state_deletions=plan.state_deletions,
    )


def test_roundtrip_two_books_restores_state_status_and_absent_state(tmp_path: Path) -> None:
    _paths, library, books = _library(tmp_path)
    backup_path = tmp_path / "reading.mangacrisp.json"
    try:
        first, second = books
        _seed_reading_metadata(library, first.id)
        library.books.upsert(first.with_updates(reading_status="completed", last_opened_at="2026-01-01T00:00:00Z"))
        # The second book intentionally has no reading_state row.  Its absent
        # state is part of the snapshot and must clear a later target row.
        library.books.upsert(second.with_updates(reading_status="reading", last_opened_at="2026-01-02T00:00:00Z"))
        document = export_reading_backup(library, backup_path)
        assert (document.book_count, document.bookmark_count) == (2, 1)

        library.reading_states.save(ReadingState(book_id=second.id, page_index=1))
        _clear_reading_metadata(library, [first.id])
        plan = preview_reading_restore(library, load_reading_backup(backup_path))
        assert plan.matched_books == 2
        assert plan.missing_books == 0
        assert plan.incompatible_books == 0
        assert plan.bookmarks_added == 1
        assert plan.state_deletions == 1

        result = restore_reading_backup(library, plan)
        assert result == _result_for_plan(plan)
        restored_first = library.books.get(first.id)
        restored_second = library.books.get(second.id)
        assert restored_first is not None and restored_second is not None
        assert (restored_first.reading_status, restored_first.last_opened_at) == (
            "completed",
            "2026-01-01T00:00:00Z",
        )
        assert (restored_second.reading_status, restored_second.last_opened_at) == (
            "reading",
            "2026-01-02T00:00:00Z",
        )
        restored_state = library.reading_states.get(first.id)
        assert restored_state is not None
        assert (restored_state.page_index, restored_state.spread_mode, restored_state.zoom) == (2, "single", 1.25)
        assert library.reading_states.get(second.id) is None
        assert [bookmark.page_index for bookmark in library.bookmarks.list_for_book(first.id)] == [1]
    finally:
        library.close()


def test_restore_is_idempotent_when_previewed_again(tmp_path: Path) -> None:
    _paths, library, books = _library(tmp_path)
    backup_path = tmp_path / "reading.mangacrisp.json"
    try:
        _seed_reading_metadata(library, books[0].id)
        document = export_reading_backup(library, backup_path)
        _clear_reading_metadata(library, [book.id for book in books])

        first_plan = preview_reading_restore(library, document)
        first_result = restore_reading_backup(library, first_plan)
        assert first_result.bookmarks_added == 1
        assert len(library.bookmarks.list_for_book(books[0].id)) == 1

        second_plan = preview_reading_restore(library, document)
        assert second_plan.bookmarks_added == 0
        assert second_plan.bookmarks_skipped == 1
        second_result = restore_reading_backup(library, second_plan)
        assert second_result.bookmarks_added == 0
        assert len(library.bookmarks.list_for_book(books[0].id)) == 1
    finally:
        library.close()


def test_export_excludes_source_paths_and_global_settings_but_keeps_user_text(tmp_path: Path) -> None:
    paths, library, books = _library(tmp_path, ("Path-like title",))
    backup_path = tmp_path / "reading.mangacrisp.json"
    cache_file = paths.cache_dir / "keep.bin"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(b"cache must stay untouched")
    try:
        library.bookmarks.add(books[0].id, 1, label="user /path/label", note="user note")
        source_path = Path(books[0].source_uri)
        export_reading_backup(library, backup_path)
        payload = backup_path.read_text(encoding="utf-8")
        assert str(source_path) not in payload
        assert "source_uri" not in payload
        assert "local_path" not in payload
        assert "settings" not in payload
        assert "user /path/label" in payload
        assert cache_file.read_bytes() == b"cache must stay untouched"
    finally:
        library.close()


def test_preview_requires_exact_id_and_file_metadata_not_title(tmp_path: Path) -> None:
    _paths, library, _books = _library(tmp_path)
    backup_path = tmp_path / "reading.mangacrisp.json"
    try:
        document = export_reading_backup(library, backup_path)
        first, second = document.books
        missing = replace(first, id="local:missing-book")
        incompatible = replace(second, title="same title is not an identity", file_kind="pdf")
        mixed = replace(document, books=(missing, incompatible))
        plan = preview_reading_restore(library, mixed)
        assert plan.matched_books == 0
        assert plan.missing_books == 1
        assert plan.missing_book_ids == ("local:missing-book",)
        assert plan.incompatible_books == 1
        assert plan.incompatible[0].reason == "file kind mismatch"
    finally:
        library.close()


def test_preview_rejects_page_count_and_position_incompatibility(tmp_path: Path) -> None:
    _paths, library, books = _library(tmp_path, ("Alpha",))
    backup_path = tmp_path / "reading.mangacrisp.json"
    try:
        _seed_reading_metadata(library, books[0].id)
        document = export_reading_backup(library, backup_path)
        backup_book = document.books[0]
        assert backup_book.reading_state is not None
        bad_state = replace(backup_book.reading_state, page_index=999)
        bad_book = replace(backup_book, reading_state=bad_state)
        plan = preview_reading_restore(library, replace(document, books=(bad_book,)))
        assert plan.matched_books == 0
        assert plan.incompatible_books == 1
        assert "reading position" in plan.incompatible[0].reason

        bad_page_count = replace(backup_book, page_count=99)
        plan = preview_reading_restore(library, replace(document, books=(bad_page_count,)))
        assert plan.incompatible_books == 1
        assert plan.incompatible[0].reason == "page count mismatch"
    finally:
        library.close()


def test_invalid_json_duplicate_keys_nan_bool_duplicate_ids_and_size_are_rejected(tmp_path: Path) -> None:
    _paths, library, _books = _library(tmp_path, ("Alpha",))
    valid_path = tmp_path / "valid.mangacrisp.json"
    try:
        export_reading_backup(library, valid_path)
        valid = json.loads(valid_path.read_text(encoding="utf-8"))

        duplicate_key = tmp_path / "duplicate-key.json"
        duplicate_key.write_text('{"format":"x","format":"y"}', encoding="utf-8")
        with pytest.raises(ReadingBackupValidationError, match="duplicate JSON key"):
            load_reading_backup(duplicate_key)

        nan_path = tmp_path / "nan.json"
        nan_payload = copy.deepcopy(valid)
        nan_payload["books"][0]["reading_state"] = {
            "page_index": 0,
            "spread_mode": "spread",
            "reading_direction": "rtl",
            "cover_single": True,
            "fit_mode": "page",
            "zoom": float("nan"),
            "pan_x": None,
            "pan_y": None,
            "correction_preset": "自然",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        nan_path.write_text(json.dumps(nan_payload, allow_nan=True), encoding="utf-8")
        with pytest.raises(ReadingBackupValidationError, match="JSON constant"):
            load_reading_backup(nan_path)

        bool_path = tmp_path / "bool-page.json"
        bool_payload = copy.deepcopy(valid)
        bool_payload["books"][0]["bookmarks"] = [
            {
                "id": "bookmark-bool",
                "page_index": True,
                "label": "bad",
                "note": None,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]
        bool_path.write_text(json.dumps(bool_payload), encoding="utf-8")
        with pytest.raises(ReadingBackupValidationError, match="must be an integer"):
            load_reading_backup(bool_path)

        duplicate_id_path = tmp_path / "duplicate-id.json"
        duplicate_payload = copy.deepcopy(valid)
        duplicate_payload["books"].append(copy.deepcopy(duplicate_payload["books"][0]))
        duplicate_id_path.write_text(json.dumps(duplicate_payload), encoding="utf-8")
        with pytest.raises(ReadingBackupValidationError, match="duplicate or empty book ID"):
            load_reading_backup(duplicate_id_path)

        oversized_path = tmp_path / "oversized.json"
        oversized_path.write_bytes(b"x" * (MAX_BACKUP_BYTES + 1))
        with pytest.raises(ReadingBackupValidationError, match="16 MiB"):
            load_reading_backup(oversized_path)
    finally:
        library.close()


def test_invalid_database_data_does_not_overwrite_existing_export(tmp_path: Path) -> None:
    _paths, library, books = _library(tmp_path, ("Alpha",))
    backup_path = tmp_path / "existing.mangacrisp.json"
    try:
        backup_path.write_bytes(b"keep this old backup")
        library.db.connection.execute(
            "UPDATE books SET reading_status = 'not-a-status' WHERE id = ?", (books[0].id,)
        )
        library.db.connection.commit()
        with pytest.raises(ReadingBackupValidationError):
            export_reading_backup(library, backup_path)
        assert backup_path.read_bytes() == b"keep this old backup"
    finally:
        library.close()


def test_restore_rejects_stale_preview_before_writing(tmp_path: Path) -> None:
    _paths, library, books = _library(tmp_path, ("Alpha",))
    backup_path = tmp_path / "reading.mangacrisp.json"
    try:
        document = export_reading_backup(library, backup_path)
        plan = preview_reading_restore(library, document)
        library.books.upsert(books[0].with_updates(reading_status="completed"))
        with pytest.raises(ReadingBackupStalePlan):
            restore_reading_backup(library, plan)
        assert library.books.get(books[0].id).reading_status == "completed"
    finally:
        library.close()


def test_restore_rolls_back_all_db_changes_when_bookmark_insert_fails(tmp_path: Path) -> None:
    _paths, library, books = _library(tmp_path, ("Alpha",))
    backup_path = tmp_path / "reading.mangacrisp.json"
    try:
        _seed_reading_metadata(library, books[0].id, bookmark_label="boom")
        document = export_reading_backup(library, backup_path)
        _clear_reading_metadata(library, [books[0].id])
        plan = preview_reading_restore(library, document)
        library.db.connection.executescript(
            """
            CREATE TRIGGER fail_reading_backup_bookmark
            BEFORE INSERT ON bookmarks
            WHEN NEW.label = 'boom'
            BEGIN
                SELECT RAISE(ABORT, 'synthetic restore failure');
            END;
            """
        )
        library.db.connection.commit()
        with pytest.raises(sqlite3.IntegrityError, match="synthetic restore failure"):
            restore_reading_backup(library, plan)
        assert library.books.get(books[0].id).reading_status == "unread"
        assert library.reading_states.get(books[0].id) is None
        assert library.bookmarks.list_for_book(books[0].id) == []
    finally:
        library.close()
