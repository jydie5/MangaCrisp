from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from mangacrisp_app.cursor_autohide import (
    CURSOR_AUTO_HIDE_DELAY_MS,
    CursorAutoHideState,
    cursor_may_hide,
    cursor_must_show,
)
from mangacrisp_app.viewer import SpreadWindow


class CursorAutoHidePolicyTests(unittest.TestCase):
    def test_delay_is_two_seconds(self) -> None:
        self.assertEqual(CURSOR_AUTO_HIDE_DELAY_MS, 2000)

    def test_idle_fullscreen_hides_cursor(self) -> None:
        self.assertTrue(cursor_may_hide(CursorAutoHideState(fullscreen=True)))

    def test_windowed_mode_never_hides(self) -> None:
        self.assertFalse(cursor_may_hide(CursorAutoHideState(fullscreen=False)))

    def test_blocking_conditions_keep_cursor_visible(self) -> None:
        for blocked in (
            CursorAutoHideState(fullscreen=True, window_active=False),
            CursorAutoHideState(fullscreen=True, drag_active=True),
            CursorAutoHideState(fullscreen=True, modal_open=True),
            CursorAutoHideState(fullscreen=True, pointer_over_overlay=True),
            CursorAutoHideState(fullscreen=True, closing=True),
        ):
            with self.subTest(blocked=blocked):
                self.assertFalse(cursor_may_hide(blocked))
                self.assertTrue(cursor_must_show(blocked))


class CursorAutoHideWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.pages = []
        for index in range(4):
            path = self.root / f"{index:04d}.png"
            Image.new("L", (120, 180), index * 8).save(path)
            self.pages.append(path)
        self.window = SpreadWindow(
            self.pages,
            "cursor test",
            processed_pages=list(self.pages),
            cover_single=False,
            auto_prefetch=False,
            settings_path=self.root / "settings.json",
        )
        self.window.resize(1200, 800)
        self.window.show()
        self.application.processEvents()

    def tearDown(self) -> None:
        self.window.resize_quality_timer.stop()
        self.window.display_warm_timer.stop()
        self.window.cache_maintenance_timer.stop()
        self.window.clear_queued_display_requests()
        self.window.visible_display_pool.waitForDone(2000)
        self.window.warm_display_pool.waitForDone(2000)
        self.window.close()
        self.window.deleteLater()
        self.application.processEvents()
        self.temporary_directory.cleanup()

    def idle_state(self, **overrides) -> CursorAutoHideState:
        values = {"fullscreen": self.window.is_fullscreen}
        values.update(overrides)
        return CursorAutoHideState(**values)

    def enter_fullscreen(self) -> None:
        self.window.toggle_fullscreen()
        self.application.processEvents()

    def hide_now(self) -> None:
        with patch.object(self.window, "cursor_auto_hide_state", return_value=self.idle_state()):
            self.window.hide_cursor_if_idle()

    def mouse_move(self, widget, x: int = 40, y: int = 40) -> None:
        event = QMouseEvent(
            QEvent.MouseMove,
            QPointF(x, y),
            widget.mapToGlobal(QPoint(x, y)).toPointF(),
            Qt.NoButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
        self.application.sendEvent(widget, event)

    def test_cursor_stays_visible_in_windowed_mode(self) -> None:
        self.assertFalse(self.window.is_fullscreen)
        self.assertFalse(self.window.cursor_hide_timer.isActive())
        self.window.hide_cursor_if_idle()
        self.assertFalse(self.window.cursor_hidden)

    def test_entering_fullscreen_arms_timer_and_idle_hides_cursor(self) -> None:
        self.enter_fullscreen()
        self.assertTrue(self.window.cursor_hide_timer.isActive())
        self.assertEqual(self.window.cursor_hide_timer.interval(), CURSOR_AUTO_HIDE_DELAY_MS)

        self.hide_now()

        self.assertTrue(self.window.cursor_hidden)
        self.assertEqual(self.window.image_host.cursor().shape(), Qt.BlankCursor)

    def test_mouse_move_restores_cursor_and_restarts_timer(self) -> None:
        self.enter_fullscreen()
        self.hide_now()
        self.window.cursor_hide_timer.stop()

        self.mouse_move(self.window.left)

        self.assertFalse(self.window.cursor_hidden)
        self.assertNotEqual(self.window.image_host.cursor().shape(), Qt.BlankCursor)
        self.assertTrue(self.window.cursor_hide_timer.isActive())

    def test_key_press_restores_cursor(self) -> None:
        self.enter_fullscreen()
        self.hide_now()

        self.window.note_cursor_activity()

        self.assertFalse(self.window.cursor_hidden)

    def test_drag_in_progress_does_not_hide(self) -> None:
        self.enter_fullscreen()
        self.window.mouse_press_button = Qt.LeftButton
        try:
            self.window.hide_cursor_if_idle()
        finally:
            self.window.clear_mouse_press()
        self.assertFalse(self.window.cursor_hidden)
        self.assertTrue(self.window.cursor_hide_timer.isActive())

    def test_modal_dialog_does_not_hide(self) -> None:
        self.enter_fullscreen()
        with patch.object(self.window, "cursor_auto_hide_state", return_value=self.idle_state(modal_open=True)):
            self.window.hide_cursor_if_idle()
        self.assertFalse(self.window.cursor_hidden)

    def test_pointer_over_overlay_does_not_hide(self) -> None:
        self.enter_fullscreen()
        with patch.object(
            self.window, "cursor_auto_hide_state", return_value=self.idle_state(pointer_over_overlay=True)
        ):
            self.window.hide_cursor_if_idle()
        self.assertFalse(self.window.cursor_hidden)

    def test_overlays_keep_arrow_cursor(self) -> None:
        self.assertEqual(self.window.reading_info_panel.cursor().shape(), Qt.ArrowCursor)
        self.assertEqual(self.window.next_book_banner.cursor().shape(), Qt.ArrowCursor)

    def test_leaving_fullscreen_restores_cursor_and_stops_timer(self) -> None:
        self.enter_fullscreen()
        self.hide_now()

        self.window.toggle_fullscreen()
        self.application.processEvents()

        self.assertFalse(self.window.cursor_hidden)
        self.assertFalse(self.window.cursor_hide_timer.isActive())

    def test_focus_loss_restores_cursor(self) -> None:
        self.enter_fullscreen()
        self.hide_now()

        self.application.sendEvent(self.window, QEvent(QEvent.WindowDeactivate))

        self.assertFalse(self.window.cursor_hidden)

    def test_close_restores_cursor(self) -> None:
        self.enter_fullscreen()
        self.hide_now()

        self.window.close()

        self.assertFalse(self.window.cursor_hidden)
        self.assertFalse(self.window.cursor_hide_timer.isActive())


if __name__ == "__main__":
    unittest.main()
