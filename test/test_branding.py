from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from mangacrisp_app.branding import (
    APP_BUNDLE_IDENTIFIER,
    APP_NAME,
    APP_SUPPORT_DIR,
    CACHE_DIR,
    DEFAULT_LIBRARY_DIR,
    PROJECT_URL,
)
from mangacrisp_app.library import (
    Book,
    BookshelfRepository,
    LibraryDatabase,
    LibraryPaths,
    LibraryService,
    archive_group_key_from_source_uri,
    archive_group_source_uri,
    managed_book_dir_for_book,
    migrate_legacy_application_state,
    rewrite_path_prefix,
)


def test_public_branding_constants() -> None:
    assert APP_NAME == "MangaCrisp"
    assert APP_BUNDLE_IDENTIFIER == "com.jydie5.mangacrisp"
    assert PROJECT_URL == "https://github.com/jydie5/MangaCrisp"
    assert APP_SUPPORT_DIR.name == "MangaCrisp"
    assert CACHE_DIR.name == "MangaCrisp"
    assert DEFAULT_LIBRARY_DIR.name == "MangaCrisp Library"


def test_legacy_state_migration_preserves_settings_and_cache(tmp_path: Path) -> None:
    legacy_support = tmp_path / "Application Support" / "RAIV"
    current_support = tmp_path / "Application Support" / "MangaCrisp"
    legacy_cache = tmp_path / "Caches" / "RAIV"
    current_cache = tmp_path / "Caches" / "MangaCrisp"
    legacy_support.mkdir(parents=True)
    legacy_cache.mkdir(parents=True)
    (legacy_support / "Library" / "book" / "pages").mkdir(parents=True)
    (legacy_support / "Library" / "book" / "pages" / "0001.png").write_bytes(b"page")
    (legacy_support / "settings.json").write_text(
        json.dumps({"library_dir": str(tmp_path / "RAIV Library")}),
        encoding="utf-8",
    )
    (legacy_support / "raiv.sqlite3").write_bytes(b"database")
    (legacy_cache / "enhanced.png").write_bytes(b"cache")

    migrate_legacy_application_state(
        current_support,
        legacy_app_support=legacy_support,
        cache_dir=current_cache,
        legacy_cache_dir=legacy_cache,
    )

    assert (current_support / "settings.json").is_file()
    assert (current_support / "mangacrisp.sqlite3").read_bytes() == b"database"
    assert not (current_support / "raiv.sqlite3").exists()
    assert not (current_support / "Library").exists()
    assert (legacy_support / "Library" / "book" / "pages" / "0001.png").is_file()
    assert (current_cache / "enhanced.png").read_bytes() == b"cache"


def test_legacy_state_does_not_overwrite_existing_state(tmp_path: Path) -> None:
    legacy_support = tmp_path / "legacy"
    current_support = tmp_path / "current"
    legacy_cache = tmp_path / "legacy-cache"
    current_cache = tmp_path / "current-cache"
    legacy_support.mkdir()
    current_support.mkdir()
    (legacy_cache / "upscale").mkdir(parents=True)
    (current_cache / "vendor").mkdir(parents=True)
    (legacy_support / "settings.json").write_text("legacy", encoding="utf-8")
    (current_support / "settings.json").write_text("current", encoding="utf-8")
    (legacy_cache / "upscale" / "page.png").write_bytes(b"corrected")
    (current_cache / "vendor" / "engine.zip").write_bytes(b"engine")

    migrate_legacy_application_state(
        current_support,
        legacy_app_support=legacy_support,
        cache_dir=current_cache,
        legacy_cache_dir=legacy_cache,
    )

    assert (current_support / "settings.json").read_text(encoding="utf-8") == "current"
    assert (current_cache / "upscale" / "page.png").read_bytes() == b"corrected"
    assert (current_cache / "vendor" / "engine.zip").read_bytes() == b"engine"
    assert not legacy_cache.exists()


def test_archive_group_uri_uses_current_name_and_reads_legacy_marker(tmp_path: Path) -> None:
    current_uri = archive_group_source_uri(tmp_path / "book.rar", "volume-2")

    assert "#mangacrisp-group=volume-2" in current_uri
    assert archive_group_key_from_source_uri(current_uri) == "volume-2"
    assert (
        archive_group_key_from_source_uri(f"{tmp_path / 'book.rar'}#raiv-group=volume-2")
        == "volume-2"
    )

    database = LibraryDatabase(tmp_path / "state" / "mangacrisp.sqlite3")
    repository = BookshelfRepository(database)
    repository.upsert(
        Book(
            id="local-archive-group:1234",
            title="Volume 2",
            source_uri=f"{tmp_path / 'book.rar'}#raiv-group=volume-2",
            local_path=str(tmp_path / "pages"),
            source_kind="local",
            file_kind="archive",
        )
    )
    database.migrate()
    migrated = repository.get("local-archive-group:1234")
    database.close()

    assert migrated is not None
    assert "#mangacrisp-group=volume-2" in migrated.source_uri
    assert "#raiv-group=" not in migrated.source_uri


def test_default_library_root_migration_rewrites_managed_paths(tmp_path: Path) -> None:
    legacy_library = tmp_path / "RAIV Library"
    current_library = tmp_path / "MangaCrisp Library"
    support_dir = tmp_path / "Application Support" / "MangaCrisp"
    database_path = support_dir / "mangacrisp.sqlite3"
    support_dir.mkdir(parents=True)

    book = Book(
        id="local:1234",
        title="Volume 1",
        source_uri=str(tmp_path / "source.zip"),
        local_path="",
        source_kind="local",
        file_kind="archive",
        page_count=1,
    )
    legacy_book_dir = managed_book_dir_for_book(book, legacy_library)
    pages_dir = legacy_book_dir / "pages"
    cover_dir = legacy_book_dir / "cover"
    pages_dir.mkdir(parents=True)
    cover_dir.mkdir()
    (pages_dir / "0001.png").write_bytes(b"page")
    (cover_dir / "cover.jpg").write_bytes(b"cover")
    book = book.with_updates(
        local_path=str(pages_dir),
        cover_thumbnail_path=str(cover_dir / "cover.jpg"),
    )

    database = LibraryDatabase(database_path)
    BookshelfRepository(database).upsert(book)
    database.close()
    settings_path = support_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "library_dir": str(legacy_library),
                "library_dir_confirmed": True,
            }
        ),
        encoding="utf-8",
    )

    with (
        patch("mangacrisp_app.library.APP_SUPPORT_DIR", support_dir),
        patch("mangacrisp_app.library.CACHE_DIR", tmp_path / "Caches" / "MangaCrisp"),
        patch("mangacrisp_app.library.DEFAULT_LIBRARY_DIR", current_library),
        patch("mangacrisp_app.library.LEGACY_DEFAULT_LIBRARY_DIR", legacy_library),
    ):
        paths = LibraryPaths.default()
        service = LibraryService.open(paths)
        migrated = service.books.get(book.id)
        service.close()

    assert migrated is not None
    assert migrated.local_path.startswith(str(current_library))
    assert migrated.cover_thumbnail_path is not None
    assert migrated.cover_thumbnail_path.startswith(str(current_library))
    assert Path(migrated.local_path, "0001.png").read_bytes() == b"page"
    assert not legacy_library.exists()
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["library_dir"] == str(current_library)
    assert settings["library_dir_confirmed"] is True


def test_rewrite_path_prefix_respects_path_component_boundaries(tmp_path: Path) -> None:
    legacy_library = tmp_path / "RAIV Library"
    current_library = tmp_path / "MangaCrisp Library"
    managed_path = legacy_library / "Volume 1" / "pages"
    unrelated_path = tmp_path / "RAIV Library Backup" / "Volume 1" / "pages"

    assert rewrite_path_prefix(str(managed_path), legacy_library, current_library) == str(
        current_library / "Volume 1" / "pages"
    )
    assert rewrite_path_prefix(str(unrelated_path), legacy_library, current_library) == str(
        unrelated_path
    )
