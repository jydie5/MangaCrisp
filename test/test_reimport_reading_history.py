from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from mangacrisp_app.library import (
    LibraryPaths,
    LibraryService,
    ReadingState,
    save_library_settings,
)


def _library(tmp_path: Path) -> LibraryService:
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    return LibraryService.open(paths)


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    payload = io.BytesIO()
    Image.new("RGB", (32, 48), color).save(payload, format="PNG")
    return payload.getvalue()


def _seed_history(library: LibraryService, book_id: str) -> None:
    book = library.books.get(book_id)
    assert book is not None
    library.books.upsert(
        book.with_updates(reading_status="completed", last_opened_at="2026-10-25T12:00:00Z")
    )
    library.reading_states.save(ReadingState(book_id=book_id, page_index=1, correction_preset="高画質"))
    library.bookmarks.add(book_id, 1, "keep", note="keep note")


def _assert_history_survives(library: LibraryService, book_id: str) -> None:
    book = library.books.get(book_id)
    state = library.reading_states.get(book_id)
    assert book is not None and state is not None
    assert (book.reading_status, book.last_opened_at) == ("completed", "2026-10-25T12:00:00Z")
    assert (state.page_index, state.correction_preset) == (1, "高画質")
    assert [(bookmark.page_index, bookmark.label, bookmark.note) for bookmark in library.bookmarks.list_for_book(book_id)] == [
        (1, "keep", "keep note")
    ]


@pytest.mark.parametrize("entrypoint", ["register_local_book", "register_local_books", "import_local_books"])
def test_reregistering_the_same_folder_preserves_reading_history(tmp_path: Path, entrypoint: str) -> None:
    library = _library(tmp_path)
    source = tmp_path / "folder"
    source.mkdir()
    for index in range(2):
        (source / f"{index:04d}.png").write_bytes(_png_bytes((40 + index, 80, 120)))
    try:
        first = library.register_local_book(source)
        _seed_history(library, first.id)

        result = getattr(library, entrypoint)(source)
        repeated = result[0] if isinstance(result, list) else result
        assert repeated.id == first.id
        assert (repeated.reading_status, repeated.last_opened_at) == ("completed", "2026-10-25T12:00:00Z")
        _assert_history_survives(library, first.id)
    finally:
        library.close()


def test_reimporting_the_same_archive_preserves_reading_history(tmp_path: Path) -> None:
    library = _library(tmp_path)
    source = tmp_path / "book.cbz"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("0001.png", _png_bytes((30, 80, 140)))
        archive.writestr("0002.png", _png_bytes((80, 30, 140)))
    try:
        first = library.import_local_books(source)[0]
        _seed_history(library, first.id)

        repeated = library.import_local_books(source)[0]
        assert repeated.id == first.id
        assert (repeated.reading_status, repeated.last_opened_at) == ("completed", "2026-10-25T12:00:00Z")
        _assert_history_survives(library, first.id)
    finally:
        library.close()
