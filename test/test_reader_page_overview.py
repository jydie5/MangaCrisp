from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from mangacrisp_app.i18n import tr
from mangacrisp_app.viewer import SpreadWindow, viewer_shortcuts_text


@pytest.fixture
def overview_reader(qapp, tmp_path: Path):
    pages = []
    for index in range(6):
        path = tmp_path / f"page-{index}.png"
        Image.new("RGB", (80, 120), (index * 20, 50, 140)).save(path)
        pages.append(path)
    window = SpreadWindow(pages, "overview wiring", auto_prefetch=False, settings_path=tmp_path / "settings.json")
    window.show()
    qapp.processEvents()
    window.resize_quality_timer.stop()
    yield window
    window.clear_queued_display_requests()
    window.visible_display_pool.waitForDone(5000)
    window.warm_display_pool.waitForDone(5000)
    window.close()
    window.deleteLater()
    qapp.processEvents()


@pytest.mark.parametrize("direction", ["rtl", "ltr"])
@pytest.mark.parametrize("layout,cover,expected", [("single", False, 3), ("spread", False, 2), ("spread", True, 3)])
def test_page_overview_uses_physical_page_jump(overview_reader, direction, layout, cover, expected) -> None:
    window = overview_reader
    window.reading_direction = direction
    window.cover_single = cover
    window.set_page_layout(layout)
    with patch("mangacrisp_app.page_overview.PageOverviewDialog") as dialog_type:
        dialog = dialog_type.return_value
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        dialog.selected_page_index = 3
        window.show_page_overview()
        dialog_type.assert_called_once_with(window, window.pages, 0)
        dialog.shutdown.assert_called_once()
        dialog.deleteLater.assert_called_once()
    assert window.index == expected


def test_cancelled_overview_does_not_navigate_or_request_ai(overview_reader) -> None:
    window = overview_reader
    with (
        patch("mangacrisp_app.page_overview.PageOverviewDialog") as dialog_type,
        patch.object(window, "jump_to_page") as jump,
        patch.object(window, "request_prefetch") as prefetch,
    ):
        dialog = dialog_type.return_value
        dialog.exec.return_value = QDialog.DialogCode.Rejected
        dialog.selected_page_index = None
        window.show_page_overview()
        jump.assert_not_called()
        prefetch.assert_not_called()
        dialog.shutdown.assert_called_once()


def test_overview_shortcut_is_discoverable_and_respects_text_input(overview_reader, qapp) -> None:
    window = overview_reader
    assert window.reader_action_buttons["pages"]
    assert tr("T: ページ一覧") in viewer_shortcuts_text("rtl")
    with patch.object(window, "show_page_overview") as overview:
        window.reading_page_spin.lineEdit().setFocus()
        qapp.processEvents()
        QTest.keyClick(window.reading_page_spin.lineEdit(), Qt.Key_T)
        overview.assert_not_called()
        window.setFocus()
        qapp.processEvents()
        QTest.keyClick(window, Qt.Key_T)
        overview.assert_called_once()
