from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QMessageBox

from mangacrisp_app import correction_cache
from mangacrisp_app.bookshelf import (
    BookshelfWindow,
    context_menu_target_ids,
    delete_confirmation_text,
    delete_outcome_message,
)
from mangacrisp_app.correction_cache import (
    CorrectionDiskCache,
    output_cache_source_key,
    remove_enhancement_cache_for_sources,
)
from mangacrisp_app.i18n import set_language
from mangacrisp_app.library import LibraryPaths, LibraryService, save_library_settings
from mangacrisp_app.page_provider import PdfPageIdentityProvider


def test_context_menu_targets_follow_selection_rules() -> None:
    assert context_menu_target_ids(None, ["a", "b"]) == []
    assert context_menu_target_ids("c", ["a", "b"]) == ["c"]
    assert context_menu_target_ids("a", ["a", "b"]) == ["a", "b"]


def test_delete_confirmation_text_shows_count_and_leading_titles() -> None:
    set_language("ja")
    question, detail = delete_confirmation_text(["One"])
    assert question == "この本を本棚から削除しますか？"
    assert detail.startswith("One\n\n")

    question, detail = delete_confirmation_text(["A", "B", "C", "D", "E"])
    assert question == "5冊を本棚から削除しますか？"
    assert detail.splitlines()[:4] == ["A", "B", "C", "ほか2冊"]
    assert "元のZIP/RAR/7zファイルは削除しません" in detail


def test_delete_outcome_message_reports_partial_failures() -> None:
    set_language("ja")
    assert delete_outcome_message(["A"], []) == "本棚から削除しました: A"
    assert delete_outcome_message(["A", "B"], []) == "2冊を本棚から削除しました。"
    assert delete_outcome_message([], ["A"]) == "削除できませんでした: A"
    assert delete_outcome_message(["A"], ["B", "C"]) == "1冊を削除しました。削除できませんでした: B, C"


def test_remove_enhancement_cache_for_sources_only_touches_matching_keys(tmp_path: Path) -> None:
    source = tmp_path / "page.png"
    Image.new("L", (8, 8), 0).save(source)
    other = tmp_path / "other.png"
    Image.new("L", (8, 8), 0).save(other)
    cache_root = tmp_path / "cache"
    for parameter_key in ("se-n0-s2", "pro-n3-s2"):
        for src in (source, other):
            folder = cache_root / "interactive" / parameter_key / output_cache_source_key(src)
            folder.mkdir(parents=True)
            (folder / "0001.png").write_bytes(b"x")

    removed = remove_enhancement_cache_for_sources([source], cache_root)

    assert removed == 2
    for parameter_key in ("se-n0-s2", "pro-n3-s2"):
        assert not (cache_root / "interactive" / parameter_key / output_cache_source_key(source)).exists()
        assert (cache_root / "interactive" / parameter_key / output_cache_source_key(other)).exists()


def test_remove_pdf_enhancement_cache_uses_recorded_page_count_when_pdf_is_broken(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.pdf"
    cover = Image.new("RGB", (120, 180), (220, 30, 40))
    second = Image.new("RGB", (120, 180), (20, 40, 220))
    cover.save(source, format="PDF", save_all=True, append_images=[second])

    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    library = LibraryService.open(paths)
    window = None
    try:
        registered = library.register_local_book(source)
        library.importer.import_book(registered)
        imported = library.books.get(registered.id)
        assert imported is not None
        assert imported.page_count == 2

        cache_root = tmp_path / "upscale"
        monkeypatch.setattr(correction_cache, "DEFAULT_UPSCALE_DIR", cache_root)
        # Keep the recorded page count while making the managed source
        # unreadable.  Identity-only cleanup must still remove its AI keys.
        Path(imported.local_path).write_bytes(b"broken PDF")
        pages = PdfPageIdentityProvider(Path(imported.local_path), imported.page_count)
        cache = CorrectionDiskCache(cache_root)
        parameter_key = "se-n0-s2"
        cached_outputs = []
        for index in range(len(pages)):
            output = cache.output_path(pages, index, parameter_key, 2)
            output.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (12, 12), (230, 20, 30)).save(output, format="PNG")
            cached_outputs.append(output)

        other = tmp_path / "other.png"
        Image.new("L", (8, 8), 0).save(other)
        unrelated = cache_root / "interactive" / parameter_key / output_cache_source_key(other)
        unrelated.mkdir(parents=True)
        (unrelated / "output.png").write_bytes(b"keep")

        window = BookshelfWindow(library)
        # The cleanup must not try to parse or render the damaged PDF.
        with patch("mangacrisp_app.bookshelf.PdfPageList", side_effect=AssertionError("must stay lazy")):
            window.remove_enhancement_cache(imported)

        assert all(not output.exists() for output in cached_outputs)
        assert (unrelated / "output.png").is_file()
        assert Path(imported.local_path).is_file()
    finally:
        if window is not None:
            window.close()
        library.close()


def _bookshelf_with_books(tmp_path: Path, count: int) -> tuple[BookshelfWindow, list[str]]:
    set_language("ja")
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    library = LibraryService.open(paths)
    ids: list[str] = []
    for index in range(count):
        folder = tmp_path / f"book{index}"
        folder.mkdir()
        for page in range(3):
            Image.new("L", (40, 60), page * 20).save(folder / f"{page:03d}.png")
        ids.append(library.register_local_book(folder).id)
    window = BookshelfWindow(library)
    return window, ids


def _select_rows(window: BookshelfWindow, rows: list[int]) -> None:
    window.list_widget.clearSelection()
    for row in rows:
        window.list_widget.item(row).setSelected(True)
    window.list_widget.setCurrentRow(rows[-1])


def test_bookshelf_allows_multiple_selection_and_deletes_them_with_one_confirmation(qapp, tmp_path: Path) -> None:
    window, _ids = _bookshelf_with_books(tmp_path, 3)
    try:
        assert window.list_widget.selectionMode() == window.list_widget.SelectionMode.ExtendedSelection
        _select_rows(window, [0, 2])
        assert len(window.selected_book_ids()) == 2

        with patch.object(QMessageBox, "exec", return_value=QMessageBox.Yes) as confirm:
            window.delete_selected_book()

        assert confirm.call_count == 1
        assert window.list_widget.count() == 1
        assert len(window.library.books.list_books()) == 1
    finally:
        window.close()


def test_delete_key_uses_the_multi_selection(qapp, tmp_path: Path) -> None:
    window, _ids = _bookshelf_with_books(tmp_path, 2)
    try:
        _select_rows(window, [0, 1])
        with (
            patch.object(QMessageBox, "exec", return_value=QMessageBox.No),
            patch.object(window, "delete_books", wraps=window.delete_books) as delete_books,
        ):
                window.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
        assert delete_books.call_count == 1
        assert len(delete_books.call_args.args[0]) == 2
        assert window.list_widget.count() == 2
    finally:
        window.close()


def test_partial_failure_keeps_successful_deletions(qapp, tmp_path: Path) -> None:
    window, ids = _bookshelf_with_books(tmp_path, 2)
    try:
        original = window.library.delete_book

        def flaky_delete(book_id: str, remove_managed_storage: bool = True) -> bool:
            if book_id == ids[1]:
                raise OSError("locked")
            return original(book_id, remove_managed_storage)

        _select_rows(window, [0, 1])
        with (
            patch.object(QMessageBox, "exec", return_value=QMessageBox.Yes),
            patch.object(window.library, "delete_book", side_effect=flaky_delete),
        ):
            window.delete_selected_book()

        remaining = {book.id for book in window.library.books.list_books()}
        assert remaining == {ids[1]}
        assert "削除できませんでした" in window.status_label.text()
    finally:
        window.close()


def test_right_click_on_unselected_book_targets_only_that_book(qapp, tmp_path: Path) -> None:
    window, ids = _bookshelf_with_books(tmp_path, 3)
    try:
        _select_rows(window, [0, 1])
        item = window.list_widget.item(2)

        menu = window.build_book_context_menu(item)

        assert menu is not None
        assert window.selected_book_ids() == [item.data(Qt.UserRole)]
        assert item.data(Qt.UserRole) in ids
        assert [action.text() for action in menu.actions()] == ["読む", "進捗を変更", "本棚から削除"]
    finally:
        window.close()


def test_right_click_on_selected_book_keeps_the_multi_selection(qapp, tmp_path: Path) -> None:
    window, _ids = _bookshelf_with_books(tmp_path, 3)
    try:
        _select_rows(window, [0, 2])
        item = window.list_widget.item(0)

        menu = window.build_book_context_menu(item)

        assert menu is not None
        assert len(window.selected_book_ids()) == 2
        assert menu.actions()[-1].text() == "2冊を本棚から削除"
        assert window.build_book_context_menu(None) is None
    finally:
        window.close()
