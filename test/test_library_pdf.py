import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from mangacrisp_app.library import (
    CURRENT_SCHEMA_VERSION,
    LibraryDatabase,
    LibraryPaths,
    LibraryService,
)


def make_pdf(path: Path) -> None:
    cover = Image.new("RGB", (120, 180), (220, 30, 40))
    second = Image.new("RGB", (120, 180), (20, 40, 220))
    cover.save(path, format="PDF", save_all=True, append_images=[second])


def test_library_imports_pdf_cover_only_and_keeps_source_on_delete(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    make_pdf(source)
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    service = LibraryService.open(paths)
    try:
        book = service.register_local_book(source)
        result = service.importer.import_book(book)
        imported = service.books.get(book.id)

        assert imported is not None
        assert imported.file_kind == "pdf"
        assert imported.page_count == 2
        assert Path(imported.local_path).is_file()
        assert Path(imported.local_path) != source
        assert imported.cover_thumbnail_path is not None
        assert Path(imported.cover_thumbnail_path).is_file()
        assert len(result.page_paths) == 1
        assert len(list(result.pages_dir.glob("*.png"))) == 1

        assert service.delete_book(book.id)
        assert source.is_file()
        assert not result.book_dir.exists()
        assert not result.pages_dir.exists()
    finally:
        service.close()


def test_database_sets_schema_version_and_rejects_newer_database(tmp_path: Path) -> None:
    database_path = tmp_path / "library.sqlite3"
    database = LibraryDatabase(database_path)
    try:
        version = database.connection.execute("PRAGMA user_version").fetchone()[0]
        assert version == CURRENT_SCHEMA_VERSION
    finally:
        database.close()

    connection = sqlite3.connect(database_path)
    connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")
    connection.close()

    with pytest.raises(RuntimeError, match="newer than this app supports"):
        LibraryDatabase(database_path)


def test_database_backs_up_existing_database_before_migration(tmp_path: Path) -> None:
    database_path = tmp_path / "library.sqlite3"
    connection = sqlite3.connect(database_path)
    connection.execute("CREATE TABLE legacy_marker (value TEXT NOT NULL)")
    connection.execute("INSERT INTO legacy_marker VALUES ('preserved')")
    connection.commit()
    connection.close()

    database = LibraryDatabase(database_path)
    database.close()

    backup_path = tmp_path / "library.sqlite3.backup-v0"
    assert backup_path.is_file()
    backup = sqlite3.connect(backup_path)
    try:
        assert backup.execute("SELECT value FROM legacy_marker").fetchone()[0] == "preserved"
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 0
    finally:
        backup.close()
