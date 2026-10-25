"""Validated, metadata-only reading-state backups.

The first backup format deliberately covers one local library only.  A book is
matched by its existing ``books.id``; source paths, source files, and all
disposable caches stay outside the format.  This keeps restore useful for
recovering reading state without pretending that the current path-derived book
IDs are portable content identities.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .library import CURRENT_SCHEMA_VERSION, LibraryService, utc_now_iso

BACKUP_FORMAT = "mangacrisp-reading-backup"
BACKUP_FORMAT_VERSION = 1
BACKUP_SCOPE = "same-library"
MAX_BACKUP_BYTES = 16 * 1024 * 1024
MAX_BOOKS = 100_000
MAX_BOOKMARKS = 200_000

VALID_READING_STATUSES = frozenset({"unread", "reading", "completed"})
VALID_SPREAD_MODES = frozenset({"spread", "single"})
VALID_READING_DIRECTIONS = frozenset({"rtl", "ltr"})
VALID_FIT_MODES = frozenset({"page", "width", "height", "actual", "custom"})


class ReadingBackupError(ValueError):
    """Base error for invalid backup data or an unsafe restore operation."""


class ReadingBackupValidationError(ReadingBackupError):
    """Raised when a backup file or database snapshot fails validation."""


class ReadingBackupStalePlan(ReadingBackupError):
    """Raised when the database changed after a restore preview was created."""


@dataclass(frozen=True, slots=True)
class BackupReadingState:
    page_index: int
    spread_mode: str
    reading_direction: str
    cover_single: bool
    fit_mode: str
    zoom: float | None
    pan_x: float | None
    pan_y: float | None
    correction_preset: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class BackupBookmark:
    id: str
    page_index: int
    label: str
    note: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class BackupBook:
    id: str
    title: str
    file_kind: str
    page_count: int | None
    reading_status: str
    last_opened_at: str | None
    reading_state: BackupReadingState | None
    bookmarks: tuple[BackupBookmark, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bookmarks", tuple(self.bookmarks))


@dataclass(frozen=True, slots=True)
class ReadingBackupDocument:
    """An immutable, validated reading backup snapshot."""

    format_version: int
    database_schema_version: int
    created_at: str
    books: tuple[BackupBook, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "books", tuple(self.books))
        _validate_document(self)

    @property
    def book_count(self) -> int:
        return len(self.books)

    @property
    def bookmark_count(self) -> int:
        return sum(len(book.bookmarks) for book in self.books)

    def to_payload(self) -> dict[str, Any]:
        _validate_document(self)
        return {
            "format": BACKUP_FORMAT,
            "format_version": self.format_version,
            "app": "MangaCrisp",
            "scope": BACKUP_SCOPE,
            "database_schema_version": self.database_schema_version,
            "created_at": self.created_at,
            "books": [_book_to_payload(book) for book in self.books],
        }


@dataclass(frozen=True, slots=True)
class RestoreIssue:
    book_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class BookmarkAddition:
    book_id: str
    bookmark_id: str
    page_index: int
    label: str
    note: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class ReadingRestorePlan:
    """Preview result and immutable actions for one target DB snapshot."""

    document: ReadingBackupDocument
    target_snapshot: str
    compatible_books: tuple[BackupBook, ...]
    missing_book_ids: tuple[str, ...]
    incompatible: tuple[RestoreIssue, ...]
    bookmark_additions: tuple[BookmarkAddition, ...]
    bookmarks_skipped: int
    bookmark_conflicts: int
    state_deletion_book_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "compatible_books", tuple(self.compatible_books))
        object.__setattr__(self, "missing_book_ids", tuple(self.missing_book_ids))
        object.__setattr__(self, "incompatible", tuple(self.incompatible))
        object.__setattr__(self, "bookmark_additions", tuple(self.bookmark_additions))
        object.__setattr__(self, "state_deletion_book_ids", tuple(self.state_deletion_book_ids))

    @property
    def matched_books(self) -> int:
        return len(self.compatible_books)

    @property
    def missing_books(self) -> int:
        return len(self.missing_book_ids)

    @property
    def incompatible_books(self) -> int:
        return len(self.incompatible)

    @property
    def bookmarks_added(self) -> int:
        return len(self.bookmark_additions)

    @property
    def state_deletions(self) -> int:
        return len(self.state_deletion_book_ids)

    @property
    def matched_count(self) -> int:
        return self.matched_books

    @property
    def missing_count(self) -> int:
        return self.missing_books

    @property
    def incompatible_count(self) -> int:
        return self.incompatible_books


@dataclass(frozen=True, slots=True)
class ReadingRestoreResult:
    matched_books: int
    missing_books: int
    incompatible_books: int
    bookmarks_added: int
    bookmarks_skipped: int
    bookmark_conflicts: int
    state_deletions: int


def export_reading_backup(library: LibraryService, path: str | Path) -> ReadingBackupDocument:
    """Export reading metadata atomically, without media or cache data."""

    document = _document_from_database(library)
    payload = json.dumps(
        document.to_payload(),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    if len(payload) > MAX_BACKUP_BYTES:
        raise ReadingBackupValidationError("reading backup exceeds the 16 MiB limit")
    _atomic_write(Path(path), payload)
    return document


def load_reading_backup(path: str | Path) -> ReadingBackupDocument:
    """Load and strictly validate one metadata-only backup file."""

    source = Path(path).expanduser()
    try:
        if not source.is_file():
            raise ReadingBackupValidationError(f"backup file does not exist: {source}")
        with source.open("rb") as handle:
            raw = handle.read(MAX_BACKUP_BYTES + 1)
    except ReadingBackupValidationError:
        raise
    except OSError as exc:
        raise ReadingBackupError(f"could not read reading backup: {source}") from exc
    if len(raw) > MAX_BACKUP_BYTES:
        raise ReadingBackupValidationError("reading backup exceeds the 16 MiB limit")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except ReadingBackupValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ReadingBackupValidationError("invalid UTF-8 JSON reading backup") from exc
    document = _document_from_payload(value)
    _validate_document(document)
    return document


def preview_reading_restore(
    library: LibraryService,
    document: ReadingBackupDocument,
) -> ReadingRestorePlan:
    """Create a restore plan against an immutable snapshot of ``library``."""

    _validate_document(document)
    _validate_target_schema(library, document)
    target_snapshot = _target_snapshot(library)
    target_books = _target_books(library)
    target_bookmarks = _target_bookmarks(library)
    target_bookmark_owners = {
        bookmark_id: book_id
        for book_id, bookmarks in target_bookmarks.items()
        for bookmark_id in bookmarks
    }

    compatible: list[BackupBook] = []
    missing: list[str] = []
    incompatible: list[RestoreIssue] = []
    state_deletions: list[str] = []
    for backup_book in document.books:
        target_book = target_books.get(backup_book.id)
        if target_book is None:
            missing.append(backup_book.id)
            continue
        reason = _compatibility_reason(backup_book, target_book)
        if reason is not None:
            incompatible.append(RestoreIssue(backup_book.id, reason))
            continue
        compatible.append(backup_book)
        if backup_book.reading_state is None:
            state_deletions.append(backup_book.id)

    additions: list[BookmarkAddition] = []
    bookmarks_skipped = 0
    bookmark_conflicts = 0
    used_ids = set(target_bookmark_owners)
    occupied_pages = {
        book_id: {bookmark["page_index"] for bookmark in bookmarks.values()}
        for book_id, bookmarks in target_bookmarks.items()
    }
    for backup_book in compatible:
        book_pages = occupied_pages.setdefault(backup_book.id, set())
        for bookmark in backup_book.bookmarks:
            if bookmark.page_index in book_pages:
                bookmarks_skipped += 1
                continue
            bookmark_id = bookmark.id
            if bookmark_id in used_ids:
                bookmark_conflicts += 1
                bookmark_id = _fresh_bookmark_id(used_ids)
            used_ids.add(bookmark_id)
            book_pages.add(bookmark.page_index)
            additions.append(
                BookmarkAddition(
                    book_id=backup_book.id,
                    bookmark_id=bookmark_id,
                    page_index=bookmark.page_index,
                    label=bookmark.label,
                    note=bookmark.note,
                    created_at=bookmark.created_at,
                    updated_at=bookmark.updated_at,
                )
            )

    return ReadingRestorePlan(
        document=document,
        target_snapshot=target_snapshot,
        compatible_books=tuple(compatible),
        missing_book_ids=tuple(missing),
        incompatible=tuple(incompatible),
        bookmark_additions=tuple(additions),
        bookmarks_skipped=bookmarks_skipped,
        bookmark_conflicts=bookmark_conflicts,
        state_deletion_book_ids=tuple(state_deletions),
    )


def restore_reading_backup(
    library: LibraryService,
    plan: ReadingRestorePlan,
) -> ReadingRestoreResult:
    """Apply a previously previewed plan in one SQLite transaction."""

    if not isinstance(plan, ReadingRestorePlan):
        raise ReadingBackupError("restore requires a ReadingRestorePlan")
    _validate_document(plan.document)
    _validate_target_schema(library, plan.document)
    connection = _connection(library)
    if connection.in_transaction:
        raise ReadingBackupError("cannot restore while another database transaction is active")

    connection.execute("BEGIN IMMEDIATE")
    try:
        if _target_snapshot(library) != plan.target_snapshot:
            raise ReadingBackupStalePlan("library changed after restore preview")
        now = utc_now_iso()
        for backup_book in plan.compatible_books:
            cursor = connection.execute(
                """
                UPDATE books
                SET reading_status = ?, last_opened_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (backup_book.reading_status, backup_book.last_opened_at, now, backup_book.id),
            )
            if cursor.rowcount != 1:
                raise ReadingBackupStalePlan(f"book disappeared during restore: {backup_book.id}")
            state = backup_book.reading_state
            if state is None:
                connection.execute("DELETE FROM reading_state WHERE book_id = ?", (backup_book.id,))
            else:
                connection.execute(
                    """
                    INSERT INTO reading_state (
                        book_id, page_index, spread_mode, reading_direction, cover_single,
                        fit_mode, zoom, pan_x, pan_y, correction_preset, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(book_id) DO UPDATE SET
                        page_index = excluded.page_index,
                        spread_mode = excluded.spread_mode,
                        reading_direction = excluded.reading_direction,
                        cover_single = excluded.cover_single,
                        fit_mode = excluded.fit_mode,
                        zoom = excluded.zoom,
                        pan_x = excluded.pan_x,
                        pan_y = excluded.pan_y,
                        correction_preset = excluded.correction_preset,
                        updated_at = excluded.updated_at
                    """,
                    (
                        backup_book.id,
                        state.page_index,
                        state.spread_mode,
                        state.reading_direction,
                        int(state.cover_single),
                        state.fit_mode,
                        state.zoom,
                        state.pan_x,
                        state.pan_y,
                        state.correction_preset,
                        state.updated_at,
                    ),
                )
        for addition in plan.bookmark_additions:
            connection.execute(
                """
                INSERT INTO bookmarks (
                    id, book_id, page_index, label, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    addition.bookmark_id,
                    addition.book_id,
                    addition.page_index,
                    addition.label,
                    addition.note,
                    addition.created_at,
                    addition.updated_at,
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return ReadingRestoreResult(
        matched_books=plan.matched_books,
        missing_books=plan.missing_books,
        incompatible_books=plan.incompatible_books,
        bookmarks_added=plan.bookmarks_added,
        bookmarks_skipped=plan.bookmarks_skipped,
        bookmark_conflicts=plan.bookmark_conflicts,
        state_deletions=plan.state_deletions,
    )


def _document_from_database(library: LibraryService) -> ReadingBackupDocument:
    connection = _connection(library)
    with _read_transaction(connection):
        return _document_from_database_connection(connection)


def _document_from_database_connection(connection: sqlite3.Connection) -> ReadingBackupDocument:
    schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    book_rows = connection.execute(
        """
        SELECT id, title, file_kind, page_count, reading_status, last_opened_at
        FROM books
        ORDER BY id
        """
    ).fetchall()
    state_rows = connection.execute(
        """
        SELECT book_id, page_index, spread_mode, reading_direction, cover_single,
               fit_mode, zoom, pan_x, pan_y, correction_preset, updated_at
        FROM reading_state
        ORDER BY book_id
        """
    ).fetchall()
    bookmark_rows = connection.execute(
        """
        SELECT id, book_id, page_index, label, note, created_at, updated_at
        FROM bookmarks
        ORDER BY book_id, page_index, id
        """
    ).fetchall()
    book_ids = {str(row["id"]) for row in book_rows}
    states: dict[str, BackupReadingState] = {}
    for row in state_rows:
        book_id = str(row["book_id"])
        if book_id not in book_ids or book_id in states:
            raise ReadingBackupValidationError(f"invalid reading state reference: {book_id}")
        states[book_id] = BackupReadingState(
            page_index=row["page_index"],
            spread_mode=row["spread_mode"],
            reading_direction=row["reading_direction"],
            cover_single=bool(row["cover_single"]),
            fit_mode=row["fit_mode"],
            zoom=row["zoom"],
            pan_x=row["pan_x"],
            pan_y=row["pan_y"],
            correction_preset=row["correction_preset"],
            updated_at=row["updated_at"],
        )
    bookmarks: dict[str, list[BackupBookmark]] = {book_id: [] for book_id in book_ids}
    seen_bookmark_ids: set[str] = set()
    for row in bookmark_rows:
        bookmark_id = str(row["id"])
        book_id = str(row["book_id"])
        if book_id not in book_ids or bookmark_id in seen_bookmark_ids:
            raise ReadingBackupValidationError(f"invalid bookmark reference: {bookmark_id}")
        seen_bookmark_ids.add(bookmark_id)
        bookmarks[book_id].append(
            BackupBookmark(
                id=bookmark_id,
                page_index=row["page_index"],
                label=row["label"],
                note=row["note"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        )
    document = ReadingBackupDocument(
        format_version=BACKUP_FORMAT_VERSION,
        database_schema_version=schema_version,
        created_at=utc_now_iso(),
        books=tuple(
            BackupBook(
                id=row["id"],
                title=row["title"],
                file_kind=row["file_kind"],
                page_count=row["page_count"],
                reading_status=row["reading_status"],
                last_opened_at=row["last_opened_at"],
                reading_state=states.get(row["id"]),
                bookmarks=tuple(bookmarks[row["id"]]),
            )
            for row in book_rows
        ),
    )
    return document


def _document_from_payload(value: object) -> ReadingBackupDocument:
    root = _object(value, "backup root")
    _keys(root, {"format", "format_version", "app", "scope", "database_schema_version", "created_at", "books"})
    if root["format"] != BACKUP_FORMAT:
        raise ReadingBackupValidationError("unsupported reading backup format")
    if root["app"] != "MangaCrisp" or root["scope"] != BACKUP_SCOPE:
        raise ReadingBackupValidationError("reading backup is not a MangaCrisp same-library backup")
    books_value = _list(root["books"], "books")
    books: list[BackupBook] = []
    for index, book_payload in enumerate(books_value):
        book_value = _object(book_payload, f"books[{index}]")
        _keys(
            book_value,
            {"id", "title", "file_kind", "page_count", "reading_status", "last_opened_at", "reading_state", "bookmarks"},
        )
        state_value = book_value["reading_state"]
        state = None if state_value is None else _state_from_payload(state_value, f"books[{index}].reading_state")
        bookmark_values = _list(book_value["bookmarks"], f"books[{index}].bookmarks")
        bookmarks = tuple(
            _bookmark_from_payload(item, f"books[{index}].bookmarks[{bookmark_index}]")
            for bookmark_index, item in enumerate(bookmark_values)
        )
        books.append(
            BackupBook(
                id=_string(book_value["id"], f"books[{index}].id", max_length=256),
                title=_string(book_value["title"], f"books[{index}].title", max_length=1024),
                file_kind=_string(book_value["file_kind"], f"books[{index}].file_kind", max_length=64),
                page_count=_page_count(book_value["page_count"], f"books[{index}].page_count"),
                reading_status=_status(book_value["reading_status"], f"books[{index}].reading_status"),
                last_opened_at=_optional_timestamp(
                    book_value["last_opened_at"], f"books[{index}].last_opened_at"
                ),
                reading_state=state,
                bookmarks=bookmarks,
            )
        )
    return ReadingBackupDocument(
        format_version=_integer(root["format_version"], "format_version", minimum=1),
        database_schema_version=_integer(
            root["database_schema_version"], "database_schema_version", minimum=1
        ),
        created_at=_timestamp(root["created_at"], "created_at"),
        books=tuple(books),
    )


def _state_from_payload(value: object, label: str) -> BackupReadingState:
    state = _object(value, label)
    _keys(
        state,
        {
            "page_index",
            "spread_mode",
            "reading_direction",
            "cover_single",
            "fit_mode",
            "zoom",
            "pan_x",
            "pan_y",
            "correction_preset",
            "updated_at",
        },
    )
    spread_mode = _string(state["spread_mode"], f"{label}.spread_mode", max_length=32)
    direction = _string(state["reading_direction"], f"{label}.reading_direction", max_length=32)
    fit_mode = _string(state["fit_mode"], f"{label}.fit_mode", max_length=32)
    if spread_mode not in VALID_SPREAD_MODES:
        raise ReadingBackupValidationError(f"invalid {label}.spread_mode")
    if direction not in VALID_READING_DIRECTIONS:
        raise ReadingBackupValidationError(f"invalid {label}.reading_direction")
    if fit_mode not in VALID_FIT_MODES:
        raise ReadingBackupValidationError(f"invalid {label}.fit_mode")
    return BackupReadingState(
        page_index=_integer(state["page_index"], f"{label}.page_index", minimum=0),
        spread_mode=spread_mode,
        reading_direction=direction,
        cover_single=_boolean(state["cover_single"], f"{label}.cover_single"),
        fit_mode=fit_mode,
        zoom=_optional_number(state["zoom"], f"{label}.zoom", minimum=0.01, maximum=100.0),
        pan_x=_optional_number(state["pan_x"], f"{label}.pan_x", minimum=-1_000_000_000, maximum=1_000_000_000),
        pan_y=_optional_number(state["pan_y"], f"{label}.pan_y", minimum=-1_000_000_000, maximum=1_000_000_000),
        correction_preset=_string(state["correction_preset"], f"{label}.correction_preset", max_length=128),
        updated_at=_timestamp(state["updated_at"], f"{label}.updated_at"),
    )


def _bookmark_from_payload(value: object, label: str) -> BackupBookmark:
    bookmark = _object(value, label)
    _keys(bookmark, {"id", "page_index", "label", "note", "created_at", "updated_at"})
    note = bookmark["note"]
    if note is not None:
        note = _string(note, f"{label}.note", max_length=4096)
    return BackupBookmark(
        id=_string(bookmark["id"], f"{label}.id", max_length=256),
        page_index=_integer(bookmark["page_index"], f"{label}.page_index", minimum=0),
        label=_string(bookmark["label"], f"{label}.label", max_length=1024),
        note=note,
        created_at=_timestamp(bookmark["created_at"], f"{label}.created_at"),
        updated_at=_timestamp(bookmark["updated_at"], f"{label}.updated_at"),
    )


def _validate_document(document: ReadingBackupDocument) -> None:
    if type(document.format_version) is not int or document.format_version != BACKUP_FORMAT_VERSION:
        raise ReadingBackupValidationError("unsupported reading backup version")
    if (
        type(document.database_schema_version) is not int
        or document.database_schema_version < 1
        or document.database_schema_version > CURRENT_SCHEMA_VERSION
    ):
        raise ReadingBackupValidationError("unsupported source database schema version")
    _timestamp(document.created_at, "created_at")
    if len(document.books) > MAX_BOOKS:
        raise ReadingBackupValidationError("reading backup contains too many books")
    seen_book_ids: set[str] = set()
    seen_bookmark_ids: set[str] = set()
    bookmark_count = 0
    for index, book in enumerate(document.books):
        if not isinstance(book, BackupBook):
            raise ReadingBackupValidationError(f"books[{index}] is not a backup book")
        book_id = _string(book.id, f"books[{index}].id", max_length=256)
        if not book_id or book_id in seen_book_ids:
            raise ReadingBackupValidationError(f"duplicate or empty book ID: {book_id!r}")
        seen_book_ids.add(book_id)
        _string(book.title, f"books[{index}].title", max_length=1024)
        _string(book.file_kind, f"books[{index}].file_kind", max_length=64)
        _page_count(book.page_count, f"books[{index}].page_count")
        _status(book.reading_status, f"books[{index}].reading_status")
        _optional_timestamp(book.last_opened_at, f"books[{index}].last_opened_at")
        if book.reading_state is not None:
            _validate_state(book.reading_state, f"books[{index}].reading_state")
        bookmark_count += len(book.bookmarks)
        if bookmark_count > MAX_BOOKMARKS:
            raise ReadingBackupValidationError("reading backup contains too many bookmarks")
        for bookmark_index, bookmark in enumerate(book.bookmarks):
            if not isinstance(bookmark, BackupBookmark):
                raise ReadingBackupValidationError(f"books[{index}].bookmarks[{bookmark_index}] is invalid")
            bookmark_id = _string(
                bookmark.id,
                f"books[{index}].bookmarks[{bookmark_index}].id",
                max_length=256,
            )
            if not bookmark_id or bookmark_id in seen_bookmark_ids:
                raise ReadingBackupValidationError(f"duplicate or empty bookmark ID: {bookmark_id!r}")
            seen_bookmark_ids.add(bookmark_id)
            _integer(bookmark.page_index, f"books[{index}].bookmarks[{bookmark_index}].page_index", minimum=0)
            _string(bookmark.label, f"books[{index}].bookmarks[{bookmark_index}].label", max_length=1024)
            if bookmark.note is not None:
                _string(bookmark.note, f"books[{index}].bookmarks[{bookmark_index}].note", max_length=4096)
            _timestamp(bookmark.created_at, f"books[{index}].bookmarks[{bookmark_index}].created_at")
            _timestamp(bookmark.updated_at, f"books[{index}].bookmarks[{bookmark_index}].updated_at")


def _validate_state(state: BackupReadingState, label: str) -> None:
    _integer(state.page_index, f"{label}.page_index", minimum=0)
    spread_mode = _string(state.spread_mode, f"{label}.spread_mode", max_length=32)
    direction = _string(state.reading_direction, f"{label}.reading_direction", max_length=32)
    fit_mode = _string(state.fit_mode, f"{label}.fit_mode", max_length=32)
    if spread_mode not in VALID_SPREAD_MODES:
        raise ReadingBackupValidationError(f"invalid {label}.spread_mode")
    if direction not in VALID_READING_DIRECTIONS:
        raise ReadingBackupValidationError(f"invalid {label}.reading_direction")
    if fit_mode not in VALID_FIT_MODES:
        raise ReadingBackupValidationError(f"invalid {label}.fit_mode")
    _boolean(state.cover_single, f"{label}.cover_single")
    _optional_number(state.zoom, f"{label}.zoom", minimum=0.01, maximum=100.0)
    _optional_number(state.pan_x, f"{label}.pan_x", minimum=-1_000_000_000, maximum=1_000_000_000)
    _optional_number(state.pan_y, f"{label}.pan_y", minimum=-1_000_000_000, maximum=1_000_000_000)
    _string(state.correction_preset, f"{label}.correction_preset", max_length=128)
    _timestamp(state.updated_at, f"{label}.updated_at")


def _target_books(library: LibraryService) -> dict[str, sqlite3.Row]:
    connection = _connection(library)
    return {
        str(row["id"]): row
        for row in connection.execute(
            "SELECT id, file_kind, page_count FROM books ORDER BY id"
        ).fetchall()
    }


def _target_bookmarks(library: LibraryService) -> dict[str, dict[str, sqlite3.Row]]:
    connection = _connection(library)
    result: dict[str, dict[str, sqlite3.Row]] = {}
    for row in connection.execute(
        "SELECT id, book_id, page_index, label, note, created_at, updated_at FROM bookmarks ORDER BY book_id, id"
    ).fetchall():
        result.setdefault(str(row["book_id"]), {})[str(row["id"])] = row
    return result


def _compatibility_reason(backup_book: BackupBook, target_book: sqlite3.Row) -> str | None:
    if backup_book.file_kind != target_book["file_kind"]:
        return "file kind mismatch"
    if backup_book.page_count != target_book["page_count"]:
        return "page count mismatch"
    page_count = target_book["page_count"]
    if backup_book.reading_state is not None and not _page_in_range(
        backup_book.reading_state.page_index, page_count
    ):
        return "reading position is outside the current page count"
    for bookmark in backup_book.bookmarks:
        if not _page_in_range(bookmark.page_index, page_count):
            return "bookmark position is outside the current page count"
    return None


def _page_in_range(page_index: int, page_count: int | None) -> bool:
    return page_count is not None and 0 <= page_index < page_count


def _target_snapshot(library: LibraryService) -> str:
    connection = _connection(library)
    if connection.in_transaction:
        return _target_snapshot_connection(connection)
    with _read_transaction(connection):
        return _target_snapshot_connection(connection)


def _target_snapshot_connection(connection: sqlite3.Connection) -> str:
    digest = sha256()
    schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    _hash_snapshot_value(digest, ("schema", schema_version))
    queries = (
        (
            "books",
            """
            SELECT id, title, source_uri, local_path, source_kind, file_kind,
                   page_count, cover_page_index, cover_thumbnail_path,
                   reading_status, last_opened_at, created_at, updated_at
            FROM books ORDER BY id
            """,
        ),
        (
            "reading_state",
            """
            SELECT book_id, page_index, spread_mode, reading_direction, cover_single,
                   fit_mode, zoom, pan_x, pan_y, correction_preset, updated_at
            FROM reading_state ORDER BY book_id
            """,
        ),
        (
            "bookmarks",
            """
            SELECT id, book_id, page_index, label, note, created_at, updated_at
            FROM bookmarks ORDER BY book_id, id
            """,
        ),
    )
    for table, query in queries:
        _hash_snapshot_value(digest, ("table", table))
        for row in connection.execute(query).fetchall():
            _hash_snapshot_value(digest, tuple(row))
    return digest.hexdigest()


def _hash_snapshot_value(digest: Any, value: object) -> None:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    digest.update(len(encoded).to_bytes(8, "big"))
    digest.update(encoded)


def _validate_target_schema(library: LibraryService, document: ReadingBackupDocument) -> None:
    connection = _connection(library)
    current = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if current != document.database_schema_version:
        raise ReadingBackupValidationError(
            f"backup schema {document.database_schema_version} does not match current schema {current}"
        )


def _connection(library: LibraryService) -> sqlite3.Connection:
    try:
        connection = library.db.connection
    except AttributeError as exc:
        raise ReadingBackupError("library does not expose its database connection") from exc
    if not isinstance(connection, sqlite3.Connection):
        raise ReadingBackupError("library database connection is not SQLite")
    return connection


@contextmanager
def _read_transaction(connection: sqlite3.Connection):
    if connection.in_transaction:
        raise ReadingBackupError("cannot snapshot while another database transaction is active")
    connection.execute("BEGIN")
    try:
        yield
    except Exception:
        connection.rollback()
        raise
    else:
        connection.rollback()


def _fresh_bookmark_id(used_ids: set[str]) -> str:
    candidate = str(uuid.uuid4())
    while candidate in used_ids:
        candidate = str(uuid.uuid4())
    return candidate


def _atomic_write(path: Path, payload: bytes) -> None:
    target = path.expanduser()
    if target.exists() and target.is_dir():
        raise ReadingBackupError(f"backup path is a directory: {target}")
    temporary: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
    except ReadingBackupError:
        raise
    except OSError as exc:
        raise ReadingBackupError(f"could not write reading backup: {target}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _book_to_payload(book: BackupBook) -> dict[str, Any]:
    state = book.reading_state
    return {
        "id": book.id,
        "title": book.title,
        "file_kind": book.file_kind,
        "page_count": book.page_count,
        "reading_status": book.reading_status,
        "last_opened_at": book.last_opened_at,
        "reading_state": (
            {
                "page_index": state.page_index,
                "spread_mode": state.spread_mode,
                "reading_direction": state.reading_direction,
                "cover_single": state.cover_single,
                "fit_mode": state.fit_mode,
                "zoom": state.zoom,
                "pan_x": state.pan_x,
                "pan_y": state.pan_y,
                "correction_preset": state.correction_preset,
                "updated_at": state.updated_at,
            }
            if state is not None
            else None
        ),
        "bookmarks": [
            {
                "id": bookmark.id,
                "page_index": bookmark.page_index,
                "label": bookmark.label,
                "note": bookmark.note,
                "created_at": bookmark.created_at,
                "updated_at": bookmark.updated_at,
            }
            for bookmark in book.bookmarks
        ],
    }


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReadingBackupValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ReadingBackupValidationError(f"JSON constant is not allowed: {value}")


def _keys(value: dict[str, object], expected: set[str]) -> None:
    actual = set(value)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise ReadingBackupValidationError(f"missing JSON fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ReadingBackupValidationError(f"unknown JSON fields: {', '.join(sorted(unknown))}")


def _object(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ReadingBackupValidationError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[object]:
    if type(value) is not list:
        raise ReadingBackupValidationError(f"{label} must be an array")
    return value


def _string(value: object, label: str, *, max_length: int) -> str:
    if type(value) is not str or not value or len(value) > max_length:
        raise ReadingBackupValidationError(f"{label} must be a non-empty string of at most {max_length} characters")
    return value


def _integer(value: object, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise ReadingBackupValidationError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ReadingBackupValidationError(f"{label} is below the minimum")
    return value


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ReadingBackupValidationError(f"{label} must be a boolean")
    return value


def _number(value: object, label: str, *, minimum: float, maximum: float) -> float:
    if type(value) not in {int, float} or isinstance(value, bool):
        raise ReadingBackupValidationError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise ReadingBackupValidationError(f"{label} is outside its allowed range")
    return result


def _optional_number(
    value: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float | None:
    if value is None:
        return None
    return _number(value, label, minimum=minimum, maximum=maximum)


def _page_count(value: object, label: str) -> int | None:
    if value is None:
        return None
    return _integer(value, label, minimum=0)


def _status(value: object, label: str) -> str:
    status = _string(value, label, max_length=32)
    if status not in VALID_READING_STATUSES:
        raise ReadingBackupValidationError(f"invalid {label}")
    return status


def _timestamp(value: object, label: str) -> str:
    if type(value) is not str or not value or len(value) > 64:
        raise ReadingBackupValidationError(f"{label} must be an ISO timestamp")
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReadingBackupValidationError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ReadingBackupValidationError(f"{label} must include a timezone")
    return value


def _optional_timestamp(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _timestamp(value, label)
