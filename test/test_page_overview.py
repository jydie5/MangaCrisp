from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QWidget

from mangacrisp_app.page_overview import PageOverviewDialog
from mangacrisp_app.page_provider import PdfPageList
from mangacrisp_app.page_thumbnails import ThumbnailSource


def _pages(root: Path, count: int = 40) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    pages = []
    for index in range(count):
        path = root / f"{index:04d}.png"
        Image.new("RGB", (80, 120), (20 + index, 60, 100)).save(path)
        pages.append(path)
    return pages


def test_overview_requests_only_the_visible_window_and_selects_physical_page(qapp, tmp_path: Path) -> None:
    dialog = PageOverviewDialog(None, _pages(tmp_path, 300), 150)
    dialog.resize(720, 540)
    dialog.show()
    for _ in range(4):
        qapp.processEvents()
    try:
        dialog.request_timer.stop()
        dialog.request_visible_thumbnails()
        assert len(dialog.controller.pending) < len(dialog.tiles)
        assert dialog.selected_page_index == 150
        assert dialog.tiles[150].hasFocus()
        current_center = dialog.tiles[150].mapTo(
            dialog.scroll.viewport(), dialog.tiles[150].rect().center()
        )
        assert dialog.scroll.viewport().rect().contains(current_center)
        dialog.scroll.verticalScrollBar().setValue(dialog.scroll.verticalScrollBar().maximum())
        qapp.processEvents()
        dialog.request_timer.stop()
        dialog.request_visible_thumbnails()
        pending_indexes = {index for _generation, index in dialog.controller.pending}
        assert pending_indexes
        assert min(pending_indexes) > len(dialog.tiles) // 2
        dialog.select_page(42)
        dialog.accept_selection()
        assert dialog.selected_page_index == 42
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.shutdown()
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()


def test_overview_double_click_and_outer_release_close_without_clickthrough(qapp, tmp_path: Path) -> None:
    dialog = PageOverviewDialog(None, _pages(tmp_path), 0)
    dialog.resize(720, 540)
    dialog.show()
    qapp.processEvents()
    try:
        tile = dialog.tiles[3]
        QTest.mouseDClick(tile, Qt.LeftButton, Qt.NoModifier, QPoint(10, 10))
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert dialog.selected_page_index == 3
    finally:
        dialog.shutdown()
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()

    outside = PageOverviewDialog(None, _pages(tmp_path / "outside"), 0)
    outside.resize(720, 540)
    outside.show()
    qapp.processEvents()
    try:
        QTest.mousePress(outside, Qt.LeftButton, Qt.NoModifier, QPoint(2, 2))
        QTest.mouseRelease(outside, Qt.LeftButton, Qt.NoModifier, QPoint(2, 2))
        assert outside.result() == QDialog.DialogCode.Rejected
    finally:
        outside.shutdown()
        outside.close()
        outside.deleteLater()
        qapp.processEvents()


def test_overview_covers_its_reader_parent_with_a_card_margin(qapp, tmp_path: Path) -> None:
    host = QWidget()
    host.resize(720, 540)
    reader = QWidget(host)
    reader.setGeometry(100, 80, 400, 300)
    host.show()
    dialog = PageOverviewDialog(reader, _pages(tmp_path), 0)
    dialog.show()
    qapp.processEvents()
    try:
        assert dialog.size() == host.size()
        assert dialog.pos() == host.mapToGlobal(QPoint(0, 0))
        assert dialog.card.geometry().width() < dialog.width()
        assert dialog.card.geometry().height() < dialog.height()
        assert dialog.testAttribute(Qt.WA_TranslucentBackground)
        assert dialog.card.testAttribute(Qt.WA_StyledBackground)
        backdrop = dialog.grab().toImage().pixelColor(1, 1)
        assert backdrop.alpha() > 0 and backdrop.red() < 20 and backdrop.green() < 30
    finally:
        dialog.shutdown()
        dialog.close()
        dialog.deleteLater()
        host.close()
        host.deleteLater()
        qapp.processEvents()


def test_overview_card_stays_inside_a_compact_reader_window(qapp, tmp_path: Path) -> None:
    parent = QWidget()
    parent.resize(250, 180)
    parent.show()
    dialog = PageOverviewDialog(parent, _pages(tmp_path, 1), 0)
    dialog.show()
    qapp.processEvents()
    try:
        assert dialog.card.geometry().left() >= 0
        assert dialog.card.geometry().right() < dialog.width()
        assert dialog.card.geometry().top() >= 0
        assert dialog.card.geometry().bottom() < dialog.height()
    finally:
        dialog.shutdown()
        dialog.close()
        dialog.deleteLater()
        parent.close()
        parent.deleteLater()
        qapp.processEvents()


def test_overview_retains_icons_only_for_the_requested_range(tmp_path: Path) -> None:
    dialog = PageOverviewDialog(None, _pages(tmp_path, 40), 0)
    image = QImage(12, 18, QImage.Format_RGB32)
    dialog._set_requested_indexes({0, 1})
    dialog._on_thumbnail_ready(0, image, None)
    dialog._on_thumbnail_ready(1, image, None)
    assert sum(not tile.icon().isNull() for tile in dialog.tiles) == 2
    dialog._set_requested_indexes({30, 31})
    dialog._on_thumbnail_ready(30, image, None)
    dialog._on_thumbnail_ready(31, image, None)
    assert sum(not tile.icon().isNull() for tile in dialog.tiles) == 2
    assert dialog.tiles[0].icon().isNull()


def test_overview_drag_from_backdrop_does_not_dismiss_but_escape_drains_worker(qapp, tmp_path: Path) -> None:
    dialog = PageOverviewDialog(None, _pages(tmp_path, 1), 0)
    dialog.resize(720, 540)
    dialog.show()
    qapp.processEvents()
    dialog.request_timer.stop()
    outside = QPoint(2, 2)
    inside = dialog.card.geometry().center()
    QTest.mousePress(dialog, Qt.LeftButton, Qt.NoModifier, outside)
    QTest.mouseRelease(dialog, Qt.LeftButton, Qt.NoModifier, inside)
    assert dialog.isVisible()

    original_decode = ThumbnailSource.decode

    def slow_decode(source, index, size=None):
        time.sleep(0.05)
        return original_decode(source, index, size)

    with patch.object(ThumbnailSource, "decode", slow_decode):
        dialog.controller.set_generation(100)
        dialog.controller.request([0], 100)
        deadline = time.monotonic() + 1
        while dialog.controller.pool.activeThreadCount() == 0 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert dialog.controller.pool.activeThreadCount() == 1
        QTest.keyClick(dialog, Qt.Key_Escape)
    assert not dialog.isVisible()
    assert dialog.controller.pool.activeThreadCount() == 0
    dialog.deleteLater()
    qapp.processEvents()


def test_pdf_overview_requests_only_its_visible_range_without_pdf_png_cache(qapp, tmp_path: Path) -> None:
    pdf_path = tmp_path / "overview.pdf"
    pages = [Image.new("RGB", (60, 90), (index % 255, 30, 100)) for index in range(300)]
    pages[0].save(pdf_path, format="PDF", save_all=True, append_images=pages[1:])
    provider = PdfPageList(pdf_path, cache_dir=tmp_path / "pdf-cache")
    dialog = PageOverviewDialog(None, provider, 150)
    ready: list[int] = []
    dialog.controller.thumbnail_ready.connect(lambda index, _image, _error: ready.append(index))
    dialog.resize(720, 540)
    dialog.show()
    qapp.processEvents()
    try:
        dialog.request_timer.stop()
        dialog.request_visible_thumbnails()
        requested = set(dialog._requested_indexes)
        assert requested and len(requested) < len(provider)
        assert dialog.controller.pool.waitForDone(5000)
        qapp.processEvents()
        assert ready and set(ready).issubset(requested)
        assert provider.extracted == {}
        assert not list(provider.cache_dir.glob("*.png"))
    finally:
        dialog.shutdown()
        dialog.close()
        dialog.deleteLater()
        qapp.processEvents()
