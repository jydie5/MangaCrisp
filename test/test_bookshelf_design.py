from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from mangacrisp_app.bookshelf import BOOKSHELF_STYLE_SHEET, BookshelfWindow
from mangacrisp_app.i18n import set_language
from mangacrisp_app.library import LibraryPaths, LibraryService, save_library_settings


def _bookshelf(tmp_path: Path, count: int = 0) -> BookshelfWindow:
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    library = LibraryService.open(paths)
    for index in range(count):
        folder = tmp_path / f"book-{index}"
        folder.mkdir()
        Image.new("RGB", (80, 120), (30 + index * 20, 80, 120)).save(folder / "001.png")
        library.register_local_book(folder)
    return BookshelfWindow(library)


def test_bookshelf_style_is_scoped_and_does_not_restyle_reader_siblings(
    qapp, tmp_path: Path
) -> None:
    set_language("en")
    window = _bookshelf(tmp_path)
    try:
        assert window.styleSheet() == ""
        assert window.bookshelf_page.objectName() == "bookshelfRoot"
        assert window.bookshelf_page.styleSheet() == BOOKSHELF_STYLE_SHEET
        assert "QWidget#bookshelfRoot" in BOOKSHELF_STYLE_SHEET
        assert "QMainWindow" not in BOOKSHELF_STYLE_SHEET
        assert "QWidget {" not in BOOKSHELF_STYLE_SHEET

        reader_sibling = window.stack.addWidget(QWidget())
        reader = window.stack.widget(reader_sibling)
        assert reader is not window.bookshelf_page
        assert reader.styleSheet() == ""
    finally:
        window.close()
        window.library.close()
        qapp.processEvents()


def test_bookshelf_layout_has_count_card_and_clear_primary_actions(
    qapp, tmp_path: Path
) -> None:
    set_language("en")
    window = _bookshelf(tmp_path, count=2)
    try:
        window.resize(1180, 760)
        window.show()
        qapp.processEvents()

        assert window.library_count_label.text() == "2 books / title order"
        assert window.list_widget.objectName() == "bookGrid"
        assert window.open_button.objectName() == "primaryButton"
        assert window.open_button.text() == "Read"
        assert window.add_file_button.objectName() == "secondaryButton"
        assert window.add_folder_button.objectName() == "secondaryButton"
        assert window.capture_button.objectName() == "secondaryButton"
        assert window.delete_button.objectName() == "dangerButton"
        assert window.open_button.isEnabled() is False
        assert window.delete_button.isEnabled() is False
        assert (
            window.list_widget.selectionMode()
            == window.list_widget.SelectionMode.ExtendedSelection
        )
        assert window.list_widget.geometry().width() >= 900
        assert window.open_button.height() == 40

        window.list_widget.setCurrentRow(0)
        qapp.processEvents()
        selected_id = window.list_widget.currentItem().data(Qt.UserRole)
        assert window.open_button.isEnabled()
        assert window.delete_button.isEnabled()
        with patch.object(window, "open_book") as open_book:
            window.open_button.click()
        open_book.assert_called_once_with(selected_id)
    finally:
        window.close()
        window.library.close()
        qapp.processEvents()


def test_bookshelf_remains_usable_at_narrow_english_and_japanese_sizes(
    qapp, tmp_path: Path
) -> None:
    for language in ("en", "ja"):
        set_language(language)
        window = _bookshelf(tmp_path / language, count=1)
        try:
            window.resize(1000, 680)
            window.show()
            qapp.processEvents()
            assert window.width() == 1000
            assert window.height() == 680
            assert window.list_widget.width() > 0
            assert window.open_button.isVisible()
            assert window.add_file_button.isVisible()
            assert window.add_folder_button.isVisible()
            assert window.library_location_label.isVisible()
        finally:
            window.close()
            window.library.close()
            qapp.processEvents()


def test_h_key_opens_help_when_book_grid_has_focus(qapp, tmp_path: Path) -> None:
    from PySide6.QtTest import QTest

    window = _bookshelf(tmp_path, count=1)
    try:
        window.show()
        window.list_widget.setFocus()
        qapp.processEvents()
        with patch.object(window, "show_shortcuts_help") as show_help:
            QTest.keyClick(window.list_widget, Qt.Key_H)
            show_help.assert_called_once_with()
    finally:
        window.close()
        window.library.close()
        qapp.processEvents()
