from __future__ import annotations

from pathlib import Path

from PIL import Image

from mangacrisp_app.bookshelf import BookshelfWindow
from mangacrisp_app.i18n import set_language
from mangacrisp_app.library import LibraryPaths, LibraryService, save_library_settings


def _library_with_books(tmp_path: Path, names: tuple[str, ...]):
    set_language("en")
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    library = LibraryService.open(paths)
    books = []
    sources = []
    for name in names:
        source = tmp_path / name
        source.mkdir()
        Image.new("RGB", (80, 120), (50, 90, 130)).save(source / "001.png")
        books.append(library.register_local_book(source))
        sources.append(source)
    return paths, library, books, sources


def test_bookmarks_are_deduplicated_and_survive_reopen_without_touching_source(
    qapp, tmp_path: Path
) -> None:
    paths, library, books, sources = _library_with_books(tmp_path, ("original",))
    window = BookshelfWindow(library)
    book = books[0]
    try:
        assert window.add_bookmark(book.id, 4) is True
        assert window.add_bookmark(book.id, 4) is False

        # Existing duplicate rows are retained; the new guard only prevents
        # another duplicate from being created through the bookshelf API.
        existing_duplicate = library.bookmarks.add(book.id, 4, label="legacy duplicate")
        assert window.add_bookmark(book.id, 4) is False
        restored_bookmarks = library.bookmarks.list_for_book(book.id)
        assert [bookmark.page_index for bookmark in restored_bookmarks] == [4, 4]
        assert existing_duplicate.id in {bookmark.id for bookmark in restored_bookmarks}
    finally:
        window.close()

    reopened = LibraryService.open(paths)
    try:
        restored = reopened.books.get(book.id)
        assert restored is not None
        assert len(reopened.bookmarks.list_for_book(book.id)) == 2
        assert sources[0].is_dir()
        assert (sources[0] / "001.png").is_file()
    finally:
        reopened.close()
    qapp.processEvents()


def test_bookmark_delete_only_accepts_ids_owned_by_current_book_and_keeps_books(
    qapp, tmp_path: Path
) -> None:
    _paths, library, books, sources = _library_with_books(tmp_path, ("book-a", "book-b"))
    window = BookshelfWindow(library)
    first, second = books
    try:
        first_bookmark = library.bookmarks.add(first.id, 2, label="p.3")
        second_bookmark = library.bookmarks.add(second.id, 5, label="p.6")

        assert window.delete_bookmark(first.id, second_bookmark.id) is False
        assert window.delete_bookmark(first.id, first_bookmark.id) is True
        assert window.delete_bookmark(first.id, first_bookmark.id) is False
        assert library.bookmarks.list_for_book(first.id) == []
        assert [bookmark.id for bookmark in library.bookmarks.list_for_book(second.id)] == [second_bookmark.id]
        assert library.books.get(first.id) is not None
        assert library.books.get(second.id) is not None
        assert all(source.is_dir() and (source / "001.png").is_file() for source in sources)
    finally:
        window.close()
        qapp.processEvents()
