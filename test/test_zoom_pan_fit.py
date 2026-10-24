from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mangacrisp_app.i18n import tr
from mangacrisp_app.image_viewport import SpreadViewport
from mangacrisp_app.viewer import (
    MAX_DISPLAY_DECODE_PIXELS,
    SpreadWindow,
    actual_size_zoom_factor,
    display_decode_target,
)


def _pages(root: Path, count: int = 4, size: tuple[int, int] = (1200, 1800)) -> list[Path]:
    root.mkdir(parents=True, exist_ok=True)
    pages = []
    for index in range(count):
        path = root / f"{index:04d}.png"
        Image.new("RGB", size, (40 + index, 80, 140)).save(path)
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


def test_viewport_moves_the_entire_spread_and_clamps_pan(qapp) -> None:
    viewport = SpreadViewport()
    viewport.resize(1000, 640)
    viewport.show()
    qapp.processEvents()
    try:
        assert viewport.content.geometry() == viewport.rect()
        viewport.set_zoom_factor(2.0)
        assert viewport.content.size() == QSize(2000, 1280)
        assert viewport.left.parent() is viewport.content
        assert viewport.right.parent() is viewport.content

        viewport.pan_by(-10_000, -10_000)
        assert viewport.content.x() == viewport.width() - viewport.content.width()
        assert viewport.content.y() == viewport.height() - viewport.content.height()
        viewport.pan_by(10_000, 10_000)
        assert viewport.content.pos() == QPoint(0, 0)

        viewport.reset_view()
        assert viewport.zoom_factor == 1.0
        assert viewport.content.geometry() == viewport.rect()
        viewport.set_zoom_factor(0.25)
        assert viewport.content.size() == QSize(250, 160)
        assert viewport.left.width() == viewport.right.width() == 125
    finally:
        viewport.close()
        viewport.deleteLater()
        qapp.processEvents()


def test_zoom_modes_drag_and_ctrl_wheel_only_change_display_state(qapp, tmp_path: Path) -> None:
    window = SpreadWindow(
        _pages(tmp_path),
        "zoom input",
        cover_single=False,
        auto_prefetch=False,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    try:
        window.resize_quality_timer.stop()
        window.render_spread(high_quality=True)
        initial_index = window.index
        initial_generation = window.processing_generation
        initial_processed = list(window.processed_pages)
        initial_queue = (
            window.correction_queue.pending,
            window.correction_queue.priority,
            window.correction_queue.in_flight,
        )

        window.zoom_mode_combo.setCurrentIndex(window.zoom_mode_combo.findData("width"))
        assert window.viewport.zoom_factor > 1.0
        assert window.zoom_mode_combo.currentData() == "width"
        window.zoom_mode_combo.setCurrentIndex(window.zoom_mode_combo.findData("actual"))
        assert window.zoom_mode_combo.currentData() == "actual"
        window.zoom_in()
        assert window.zoom_mode_combo.currentData() == "custom"
        assert "×" in window.zoom_value_label.text()

        # A drag begins only after the existing click tolerance.  It pans the
        # shared content and cannot also turn the page on release.
        pane = window.current_page_label()
        start = QPoint(max(20, pane.width() // 3), max(20, pane.height() // 3))
        before_pan = window.viewport.content.pos()
        QTest.mousePress(pane, Qt.LeftButton, Qt.NoModifier, start)
        QTest.mouseMove(pane, start + QPoint(70, 45), 20)
        QTest.mouseRelease(pane, Qt.LeftButton, Qt.NoModifier, start + QPoint(70, 45))
        qapp.processEvents()
        assert window.index == initial_index
        assert window.viewport.content.pos() != before_pan

        # Original comparison repaints only the labels.  The common viewport
        # transform stays fixed, so the reader does not lose its place.
        before_original_toggle = window.viewport.content.geometry()
        window.original_check.toggle()
        assert window.viewport.content.geometry() == before_original_toggle

        # Ctrl-wheel over a page zooms. Focused text controls keep their
        # normal input ownership and do not receive a reader-wide shortcut.
        local = QPoint(max(20, pane.width() // 3), max(20, pane.height() // 3))
        global_pos = pane.mapToGlobal(local)
        before_wheel = window.viewport.zoom_factor
        wheel = QWheelEvent(
            QPointF(local), QPointF(global_pos), QPoint(), QPoint(0, 120),
            Qt.NoButton, Qt.ControlModifier, Qt.ScrollUpdate, False,
        )
        QApplication.sendEvent(pane, wheel)
        assert window.viewport.zoom_factor > before_wheel
        window.reading_page_spin.setFocus()
        before_input_wheel = window.viewport.zoom_factor
        QApplication.sendEvent(
            pane,
            QWheelEvent(
                QPointF(local), QPointF(global_pos), QPoint(), QPoint(0, -120),
                Qt.NoButton, Qt.ControlModifier, Qt.ScrollUpdate, False,
            ),
        )
        assert window.viewport.zoom_factor == before_input_wheel
        assert window.processing_generation == initial_generation
        assert window.processed_pages == initial_processed
        assert (
            window.correction_queue.pending,
            window.correction_queue.priority,
            window.correction_queue.in_flight,
        ) == initial_queue
    finally:
        _close_reader(window, qapp)


def test_reading_overlay_scrolls_inside_the_available_image_area(qapp, tmp_path: Path) -> None:
    window = SpreadWindow(
        _pages(tmp_path), "compact overlay", auto_prefetch=False, settings_path=tmp_path / "settings.json"
    )
    window.resize(680, 360)
    window.show()
    qapp.processEvents()
    try:
        window.toggle_reading_info()
        qapp.processEvents()
        assert window.reading_info_scroll.widget() is window.reading_info_content
        assert window.reading_info_panel.height() <= window.image_host.height() - 24
        assert window.reading_info_bookshelf_button.parent() is window.reading_info_panel
    finally:
        _close_reader(window, qapp)


def test_reading_overlay_keeps_header_footer_fixed_and_uses_transparent_scroll_parts(qapp, tmp_path: Path) -> None:
    window = SpreadWindow(
        _pages(tmp_path), "overlay chrome", auto_prefetch=False, settings_path=tmp_path / "settings.json"
    )
    window.resize(1600, 1000)
    window.show()
    qapp.processEvents()
    try:
        window.toggle_reading_info()
        qapp.processEvents()
        assert window.reading_info_content.objectName() == "readingControlsContent"
        assert window.reading_info_scroll.objectName() == "readingControlsScroll"
        assert window.reading_info_scroll.viewport().objectName() == "readingControlsScrollViewport"
        assert window.zoom_mode_combo.objectName() == "zoomModeSelector"
        assert window.reading_info_bookshelf_button.parent() is window.reading_info_panel
        assert window.reading_info_hint.parent() is window.reading_info_panel
        assert window.reading_info_scroll.verticalScrollBar().maximum() == 0
    finally:
        _close_reader(window, qapp)


def test_capped_display_target_preserves_logical_size_via_effective_dpr() -> None:
    physical_width, physical_height, effective_dpr = display_decode_target(QSize(6000, 6000), 2.0)
    assert physical_width * physical_height <= MAX_DISPLAY_DECODE_PIXELS
    assert effective_dpr < 2.0
    assert abs(physical_width / effective_dpr - 6000) < 2
    assert abs(physical_height / effective_dpr - 6000) < 2


def test_actual_size_maps_one_source_pixel_to_one_physical_pixel_at_common_dprs() -> None:
    for dpr in (1.0, 1.25, 2.0):
        zoom = actual_size_zoom_factor(2400, 600, dpr)
        assert zoom * 600 * dpr == 2400


def test_actual_size_does_not_cap_a_wide_image_that_is_already_under_budget() -> None:
    width, height, effective_dpr = display_decode_target(
        QSize(3840, 8000), 1.0, source_size=(3840, 1080)
    )
    assert (width, height) == (3840, 1080)
    assert effective_dpr == 1.0


def test_warm_display_uses_the_visible_label_dpr_for_matching_cache_keys(qapp, tmp_path: Path) -> None:
    pages = _pages(tmp_path)
    window = SpreadWindow(
        pages,
        "warm dpr",
        cover_single=False,
        auto_prefetch=False,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    try:
        window.resize_quality_timer.stop()
        requests = []

        def capture(display_path, target, **kwargs):
            key = window.display_cache_key(
                display_path,
                target,
                kwargs["high_quality"],
                kwargs["normalize_color"],
                kwargs["source_size"],
            )
            requests.append((display_path, target, key))
            return None, key

        with patch("mangacrisp_app.viewer.target_device_pixel_ratio", return_value=2.0):
            expected = window.display_cache_key(
                pages[0], window.current_page_label(), True, False, window.image_size(0)
            )
            with patch.object(window, "request_display_pixmap", side_effect=capture):
                window.warm_display_pixmap_cache([0])
        assert any(path == pages[0] and key == expected for path, _target, key in requests)
        assert all(target in {window.left, window.right} for _path, target, _key in requests)
    finally:
        _close_reader(window, qapp)


def test_width_and_actual_focus_the_current_page_for_both_reading_directions(qapp, tmp_path: Path) -> None:
    for direction in ("rtl", "ltr"):
        window = SpreadWindow(
            _pages(tmp_path / direction, size=(320, 480)),
            f"focus {direction}",
            reading_direction=direction,
            spread_order=direction,
            cover_single=False,
            auto_prefetch=False,
            settings_path=tmp_path / f"{direction}.json",
        )
        window.resize(1200, 800)
        window.show()
        qapp.processEvents()
        try:
            window.resize_quality_timer.stop()
            for key, mode in ((Qt.Key_W, "width"), (Qt.Key_1, "actual")):
                assert window.handle_navigation_key(key)
                image_x, image_y, image_width, image_height = window.current_page_image_rect()
                viewport_x = window.viewport.content.x() + image_x
                viewport_y = window.viewport.content.y() + image_y
                if mode == "width":
                    assert abs(viewport_x) <= 1
                    assert abs(viewport_y) <= 1
                    assert abs(image_width - window.viewport.width()) <= 1
                else:
                    assert viewport_x >= 0
                    assert viewport_x + image_width <= window.viewport.width()
                    assert viewport_y >= 0
                    assert viewport_y + image_height <= window.viewport.height()
        finally:
            _close_reader(window, qapp)


def test_zoom_keys_update_mode_and_help_text(qapp, tmp_path: Path) -> None:
    window = SpreadWindow(_pages(tmp_path), "zoom keys", auto_prefetch=False, settings_path=tmp_path / "settings.json")
    window.show()
    qapp.processEvents()
    try:
        window.resize_quality_timer.stop()
        pane = window.current_page_label()
        for key, mode in ((Qt.Key_W, "width"), (Qt.Key_1, "actual"), (Qt.Key_0, "fit")):
            QTest.keyClick(pane, key)
            assert window.zoom_mode_combo.currentData() == mode
        QTest.keyClick(pane, Qt.Key_Plus)
        assert window.zoom_mode_combo.currentData() == "custom"
        before_shift_plus = window.viewport.zoom_factor
        QTest.keyClick(pane, Qt.Key_Equal, Qt.ShiftModifier)
        assert window.viewport.zoom_factor > before_shift_plus
        QTest.keyClick(pane, Qt.Key_Minus)
        assert window.zoom_mode_combo.currentData() == "custom"
        QTest.keyClick(pane, Qt.Key_Equal)
        assert window.zoom_mode_combo.currentData() == "custom"
        before_input = window.viewport.zoom_factor
        window.reading_page_spin.setFocus()
        QTest.keyClick(pane, Qt.Key_Equal, Qt.ShiftModifier)
        assert window.viewport.zoom_factor == before_input
        window.setFocus()
        window.zoom_mode_combo.showPopup()
        try:
            QTest.keyClick(pane, Qt.Key_Equal, Qt.ShiftModifier)
            assert window.viewport.zoom_factor == before_input
        finally:
            window.zoom_mode_combo.hidePopup()
        with patch("mangacrisp_app.viewer.show_help_dialog") as show_help:
            QTest.keyClick(pane, Qt.Key_H)
        assert tr("0: 全体に合わせる / W: 幅に合わせる / 1: 実寸") in show_help.call_args.args[1]
        assert tr("+ / -: 表示倍率を変更 / Ctrl/⌘+ホイール: 表示倍率を変更") in show_help.call_args.args[1]
    finally:
        _close_reader(window, qapp)


def test_width_mode_repositions_after_spread_order_swap(qapp, tmp_path: Path) -> None:
    window = SpreadWindow(
        _pages(tmp_path),
        "swap zoom",
        cover_single=False,
        auto_prefetch=False,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    try:
        window.resize_quality_timer.stop()
        assert window.handle_navigation_key(Qt.Key_W)
        window.swap_spread_order()
        image_x, image_y, image_width, _image_height = window.current_page_image_rect()
        viewport_x = window.viewport.content.x() + image_x
        assert abs(viewport_x) <= 2
        assert abs(image_width - window.viewport.width()) <= 2
        assert image_y + window.viewport.content.y() <= 2
    finally:
        _close_reader(window, qapp)


def test_double_click_release_never_consumes_the_next_click(qapp, tmp_path: Path) -> None:
    window = SpreadWindow(
        _pages(tmp_path),
        "double click",
        cover_single=False,
        auto_prefetch=False,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    try:
        window.resize_quality_timer.stop()
        pane = window.left
        point = QPoint(8, max(8, pane.height() // 2))
        QTest.mouseDClick(pane, Qt.LeftButton, Qt.NoModifier, point)
        after_double_click = window.index
        QTest.mouseClick(pane, Qt.LeftButton, Qt.NoModifier, point)
        assert window.index > after_double_click
    finally:
        _close_reader(window, qapp)


def test_auto_zoom_modes_recompute_for_page_aspect_resize_and_layout(qapp, tmp_path: Path) -> None:
    sizes = ((1200, 1600), (800, 1200), (600, 3000), (700, 1000))
    pages = []
    for index, size in enumerate(sizes):
        path = tmp_path / f"aspect-{index}.png"
        Image.new("RGB", size, (50 + index, 90, 130)).save(path)
        pages.append(path)
    window = SpreadWindow(
        pages,
        "auto zoom",
        cover_single=False,
        auto_prefetch=False,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    try:
        window.resize_quality_timer.stop()
        assert window.handle_navigation_key(Qt.Key_W)
        assert abs(window.current_page_image_rect()[2] - window.viewport.width()) <= 2
        window.move_by(2)
        assert window.zoom_mode_combo.currentData() == "width"
        assert abs(window.current_page_image_rect()[2] - window.viewport.width()) <= 2
        window.resize(1600, 800)
        qapp.processEvents()
        assert abs(window.current_page_image_rect()[2] - window.viewport.width()) <= 2
        window.set_page_layout("single")
        assert abs(window.current_page_image_rect()[2] - window.viewport.width()) <= 2

        assert window.handle_navigation_key(Qt.Key_1)
        rect = window.current_page_image_rect()
        source_width, _source_height = window.image_size(window.index)
        assert abs(rect[2] * window.viewport.devicePixelRatioF() - source_width) <= 1
        window.move_by(1)
        rect = window.current_page_image_rect()
        source_width, _source_height = window.image_size(window.index)
        assert abs(rect[2] * window.viewport.devicePixelRatioF() - source_width) <= 1
        window.resize(1300, 760)
        qapp.processEvents()
        rect = window.current_page_image_rect()
        assert abs(rect[2] * window.viewport.devicePixelRatioF() - source_width) <= 1
    finally:
        _close_reader(window, qapp)


def test_width_mode_keeps_the_visible_page_position_when_resizing(qapp, tmp_path: Path) -> None:
    window = SpreadWindow(
        _pages(tmp_path, size=(600, 3000)),
        "resize focus",
        cover_single=False,
        auto_prefetch=False,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    try:
        window.resize_quality_timer.stop()
        assert window.handle_navigation_key(Qt.Key_W)
        window.viewport.pan_by(0, -180)

        def visible_page_relative_y() -> float:
            image_x, image_y, image_width, image_height = window.current_page_image_rect()
            content = window.viewport.content.geometry()
            del image_x, image_width
            return (window.viewport.height() / 2 - content.y() - image_y) / image_height

        before = visible_page_relative_y()
        window.resize(1500, 840)
        qapp.processEvents()
        assert abs(visible_page_relative_y() - before) < 0.03
    finally:
        _close_reader(window, qapp)
