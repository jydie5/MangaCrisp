from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import Qt

from mangacrisp_app.display_cache import display_image_key
from mangacrisp_app.image_viewport import SpreadViewport
from mangacrisp_app.viewer import SpreadWindow


def _pages(root: Path, count: int = 4) -> list[Path]:
    pages = []
    for index in range(count):
        path = root / f"{index:04d}.png"
        Image.new("RGB", (80, 120), (40 + index, 80, 140)).save(path)
        pages.append(path)
    return pages


def _close_reader(window: SpreadWindow, qapp) -> None:
    window.resize_quality_timer.stop()
    window.prefetch_request_timer.stop()
    window.display_warm_timer.stop()
    window.cache_maintenance_timer.stop()
    window.clear_queued_display_requests()
    window.visible_display_pool.waitForDone(5000)
    window.warm_display_pool.waitForDone(5000)
    window.close()
    window.deleteLater()
    qapp.processEvents()


def test_viewport_keeps_existing_two_pane_fit_geometry(qapp) -> None:
    viewport = SpreadViewport()
    viewport.resize(1000, 640)
    viewport.show()
    qapp.processEvents()
    try:
        margins = viewport.page_layout.contentsMargins()
        assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (0, 0, 0, 0)
        assert viewport.page_layout.spacing() == 0
        assert viewport.page_layout.count() == 2
        assert viewport.left.objectName() == viewport.right.objectName() == "pagePane"
        assert viewport.left.minimumSize().width() == viewport.right.minimumSize().width() == 320
        assert viewport.left.minimumSize().height() == viewport.right.minimumSize().height() == 320
        assert viewport.left.hasMouseTracking() and viewport.right.hasMouseTracking()
        assert viewport.left.width() == viewport.right.width()

        viewport.set_pane_alignments(Qt.AlignRight | Qt.AlignVCenter, Qt.AlignLeft | Qt.AlignVCenter)
        assert viewport.left.alignment() == Qt.AlignRight | Qt.AlignVCenter
        assert viewport.right.alignment() == Qt.AlignLeft | Qt.AlignVCenter
        viewport.set_spread_visible(False)
        qapp.processEvents()
        assert not viewport.right.isVisible()
        assert viewport.left.width() == viewport.width()
    finally:
        viewport.close()
        viewport.deleteLater()
        qapp.processEvents()


def test_reader_viewport_preserves_fit_targets_cache_keys_and_pane_order(qapp, tmp_path: Path) -> None:
    pages = _pages(tmp_path)
    window = SpreadWindow(
        pages,
        "viewport seam",
        processed_pages=list(pages),
        auto_prefetch=False,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    try:
        window.resize_quality_timer.stop()
        window.fast_resize_render = False
        window.render_spread(high_quality=True)
        assert window.left is window.viewport.left
        assert window.right is window.viewport.right
        assert window.page_layout is window.viewport.page_layout

        # Default right-bound cover retains the existing empty-left/page-right placement.
        assert window.desired_display_keys[id(window.left)] is None
        expected_cover = display_image_key(pages[0], window.right.width(), window.right.height(), True, False)
        assert window.desired_display_keys[id(window.right)] == expected_cover

        window.cover_single = False
        window.index = 2
        window.spread_order = "rtl"
        window.render_spread(high_quality=True)
        expected_left = display_image_key(pages[3], window.left.width(), window.left.height(), True, False)
        expected_right = display_image_key(pages[2], window.right.width(), window.right.height(), True, False)
        assert window.desired_display_keys[id(window.left)] == expected_left
        assert window.desired_display_keys[id(window.right)] == expected_right
        assert window.left.alignment() == Qt.AlignRight | Qt.AlignVCenter
        assert window.right.alignment() == Qt.AlignLeft | Qt.AlignVCenter

        window.reading_direction = "ltr"
        window.spread_order = "ltr"
        window.render_spread(high_quality=True)
        expected_left = display_image_key(pages[2], window.left.width(), window.left.height(), True, False)
        expected_right = display_image_key(pages[3], window.right.width(), window.right.height(), True, False)
        assert window.desired_display_keys[id(window.left)] == expected_left
        assert window.desired_display_keys[id(window.right)] == expected_right

        window.set_page_layout("single")
        assert not window.right.isVisible()
        expected_single = display_image_key(pages[2], window.left.width(), window.left.height(), True, False)
        assert window.desired_display_keys[id(window.left)] == expected_single
        assert window.desired_display_keys[id(window.right)] is None
        assert window.left.alignment() == window.right.alignment() == Qt.AlignCenter
    finally:
        _close_reader(window, qapp)
