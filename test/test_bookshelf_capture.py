from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QMainWindow

from mangacrisp_app.bookshelf import BookshelfWindow
from mangacrisp_app.library import LibraryPaths, LibraryService, save_library_settings


def _bookshelf(tmp_path: Path) -> BookshelfWindow:
    paths = LibraryPaths.for_base_dir(tmp_path / "state")
    save_library_settings(paths, library_dir_confirmed=True)
    return BookshelfWindow(LibraryService.open(paths))


def test_windows_capture_controller_stays_in_taskbar(qapp, tmp_path: Path) -> None:
    bookshelf = _bookshelf(tmp_path)
    controller = QMainWindow()
    bookshelf.active_capture = controller  # type: ignore[assignment]
    bookshelf.show()
    controller.show()
    qapp.processEvents()

    with patch("mangacrisp_app.bookshelf.sys.platform", "win32"):
        bookshelf.on_capture_mode_changed(True)
        qapp.processEvents()

    assert not bookshelf.isVisible()
    assert controller.isVisible()
    assert controller.isMinimized()
    assert bookshelf.capture_windows_hidden

    bookshelf.on_capture_mode_changed(False)
    qapp.processEvents()

    assert bookshelf.isVisible()
    assert controller.isVisible()
    assert not controller.isMinimized()
    controller.close()
    bookshelf.close()


def test_macos_capture_controller_keeps_dock_restore_behavior(
    qapp, tmp_path: Path
) -> None:
    bookshelf = _bookshelf(tmp_path)
    controller = QMainWindow()
    bookshelf.active_capture = controller  # type: ignore[assignment]
    bookshelf.show()
    controller.show()
    qapp.processEvents()

    with patch("mangacrisp_app.bookshelf.sys.platform", "darwin"):
        bookshelf.on_capture_mode_changed(True)
        qapp.processEvents()

    assert not bookshelf.isVisible()
    assert not controller.isVisible()
    controller.close()
    bookshelf.close()
