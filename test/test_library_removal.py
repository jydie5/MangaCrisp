from __future__ import annotations

import io
import shutil
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from PySide6.QtWidgets import QMessageBox

from mangacrisp_app import library as library_module
from mangacrisp_app import viewer
from mangacrisp_app.bookshelf import BookshelfWindow
from mangacrisp_app.library import LibraryPaths, LibraryService, save_library_settings


@pytest.fixture
def service(tmp_path: Path):
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    library = LibraryService.open(paths)
    try:
        yield library
    finally:
        library.close()


def import_book(service: LibraryService, source_dir: Path, name: str):
    source = source_dir / f"{name}.zip"
    page = io.BytesIO()
    Image.new("RGB", (40, 60), (180, 30, 70)).save(page, format="PNG")
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("001.png", page.getvalue())
    book = service.register_local_book(source)
    result = service.importer.import_book(book)
    return book, result, source


def test_failed_managed_removal_preserves_database_entry(
    service, tmp_path, monkeypatch
):
    book, result, source = import_book(service, tmp_path, "locked")
    original = shutil.rmtree

    def deny_managed_directory(path, *args, **kwargs):
        if Path(path) == result.book_dir:
            if kwargs.get("ignore_errors"):
                return
            raise PermissionError("managed file is in use")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(library_module.shutil, "rmtree", deny_managed_directory)

    with pytest.raises(PermissionError, match="in use"):
        service.delete_book(book.id)

    assert service.books.get(book.id) is not None
    assert result.page_paths[0].is_file()
    assert source.is_file()


def test_removal_allows_already_missing_managed_storage(service, tmp_path):
    book, result, source = import_book(service, tmp_path, "missing")
    shutil.rmtree(result.book_dir)

    assert service.delete_book(book.id)
    assert service.books.get(book.id) is None
    assert source.is_file()


def test_removal_deletes_managed_copy_but_preserves_source(service, tmp_path):
    book, result, source = import_book(service, tmp_path, "success")
    original = source.read_bytes()

    assert service.delete_book(book.id)

    assert not result.book_dir.exists()
    assert service.books.get(book.id) is None
    assert source.read_bytes() == original


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file-sharing semantics")
def test_windows_locked_file_keeps_failed_book_and_removes_other_book(
    qapp, service, tmp_path, monkeypatch
):
    locked, locked_result, locked_source = import_book(service, tmp_path, "locked")
    removable, removed_result, removed_source = import_book(
        service, tmp_path, "removable"
    )
    source_bytes = [locked_source.read_bytes(), removed_source.read_bytes()]
    monkeypatch.setattr(viewer, "DEFAULT_UPSCALE_DIR", tmp_path / "enhancement-cache")
    window = BookshelfWindow(service)
    try:
        with (
            locked_result.page_paths[0].open("rb"),
            patch.object(QMessageBox, "exec", return_value=QMessageBox.Yes),
        ):
            window.delete_books([locked.id, removable.id])

        assert service.books.get(locked.id) is not None
        assert locked_result.page_paths[0].is_file()
        assert service.books.get(removable.id) is None
        assert not removed_result.book_dir.exists()
        assert "locked" in window.status_label.text()
        assert [locked_source.read_bytes(), removed_source.read_bytes()] == source_bytes
    finally:
        window.close()
