from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow

from mangacrisp_app.bookmark_dialog import BookmarkDialog
from mangacrisp_app.i18n import tr
from mangacrisp_app.library import Bookmark
from mangacrisp_app.viewer import SpreadWindow

_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

from test_viewer_navigation import ViewerWindowTestCase


def make_bookmark(bookmark_id: str, page_index: int, label: str) -> Bookmark:
    return Bookmark(bookmark_id, "book", page_index, label)


class BookmarkDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.parent = QMainWindow()
        self.parent.resize(900, 620)
        self.parent.show()
        self.application.processEvents()
        self.bookmarks = [
            make_bookmark("first", 1, "読んだ場面"),
            make_bookmark("second", 8, "続き"),
        ]
        self.dialog = BookmarkDialog(self.parent, self.bookmarks, 10)
        self.dialog.show()
        self.application.processEvents()

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self.parent.close()
        self.parent.deleteLater()
        self.application.processEvents()

    def _outside_point(self) -> QPoint:
        for point in (
            QPoint(8, 8),
            QPoint(self.dialog.width() - 9, 8),
            QPoint(8, self.dialog.height() - 9),
            QPoint(self.dialog.width() - 9, self.dialog.height() - 9),
        ):
            if not self.dialog.card.geometry().contains(point):
                return point
        self.fail("bookmark card covers every backdrop corner")

    def test_list_contains_physical_page_and_label(self) -> None:
        self.assertEqual(self.dialog.list_widget.count(), 2)
        self.assertIn("p.2", self.dialog.list_widget.item(0).text())
        self.assertIn("読んだ場面", self.dialog.list_widget.item(0).text())
        self.assertIn("p.9", self.dialog.list_widget.item(1).text())
        self.assertIn("続き", self.dialog.list_widget.item(1).text())

    def test_empty_state_is_explicit(self) -> None:
        dialog = BookmarkDialog(self.parent, [], 10)
        dialog.show()
        self.application.processEvents()
        try:
            self.assertEqual(dialog.list_widget.count(), 0)
            self.assertTrue(dialog.empty_label.isVisible())
            self.assertFalse(dialog.go_button.isEnabled())
            self.assertFalse(dialog.delete_button.isEnabled())
        finally:
            dialog.close()
            dialog.deleteLater()
            self.application.processEvents()

    def test_go_accepts_selected_bookmark_page(self) -> None:
        self.dialog.list_widget.setCurrentRow(1)
        self.dialog.go_button.click()
        self.application.processEvents()
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self.dialog.selected_page_index, 8)

    def test_double_click_accepts_selected_bookmark_page(self) -> None:
        item = self.dialog.list_widget.item(0)
        self.dialog.list_widget.itemDoubleClicked.emit(item)
        self.application.processEvents()
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self.dialog.selected_page_index, 1)

    def test_invalid_page_cannot_move_but_can_be_deleted(self) -> None:
        invalid = make_bookmark("invalid", 99, "消えたページ")
        deleted: list[str] = []
        dialog = BookmarkDialog(
            self.parent,
            [invalid],
            10,
            delete_callback=lambda bookmark_id: deleted.append(bookmark_id) or True,
        )
        dialog.show()
        self.application.processEvents()
        try:
            self.assertFalse(dialog.go_button.isEnabled())
            self.assertTrue(dialog.delete_button.isEnabled())
            dialog.delete_button.click()
            self.application.processEvents()
            self.assertEqual(deleted, ["invalid"])
            self.assertEqual(dialog.list_widget.count(), 0)
        finally:
            dialog.close()
            dialog.deleteLater()
            self.application.processEvents()

    def test_delete_refreshes_only_after_success(self) -> None:
        deleted: list[str] = []
        self.dialog.delete_callback = lambda bookmark_id: deleted.append(bookmark_id) or True
        self.dialog.list_widget.setCurrentRow(0)
        self.dialog._update_selection_state()
        self.dialog.delete_button.click()
        self.application.processEvents()
        self.assertEqual(deleted, ["first"])
        self.assertEqual(self.dialog.list_widget.count(), 1)
        self.assertIn("p.9", self.dialog.list_widget.item(0).text())

        self.dialog.delete_callback = lambda _bookmark_id: False
        self.dialog._update_selection_state()
        self.dialog.delete_button.click()
        self.application.processEvents()
        self.assertEqual(self.dialog.list_widget.count(), 1)
        self.assertEqual(
            self.dialog.status_label.text(),
            tr("しおりを削除できませんでした。"),
        )

    def test_escape_and_outside_release_dismiss_without_passthrough(self) -> None:
        self.dialog.close_button.setFocus(Qt.FocusReason.OtherFocusReason)
        QTest.keyClick(self.dialog.close_button, Qt.Key.Key_Escape)
        self.application.processEvents()
        self.assertFalse(self.dialog.isVisible())

        self.dialog.show()
        self.application.processEvents()
        point = self._outside_point()
        QTest.mousePress(self.dialog, Qt.MouseButton.LeftButton, pos=point)
        self.application.processEvents()
        self.assertTrue(self.dialog.isVisible())
        QTest.mouseRelease(self.dialog, Qt.MouseButton.LeftButton, pos=point)
        self.application.processEvents()
        self.assertFalse(self.dialog.isVisible())


class BookmarkViewerIntegrationTests(ViewerWindowTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bookmarks = [make_bookmark("first", 6, "続き")]
        self.window.bookmarks_provider = lambda: list(self.bookmarks)

    def test_shift_b_opens_bookmark_list_action(self) -> None:
        with patch.object(self.window, "show_bookmarks") as show_bookmarks:
            self.assertTrue(self.window.handle_navigation_key(Qt.Key.Key_B, Qt.KeyboardModifier.ShiftModifier))
        show_bookmarks.assert_called_once_with()

    def test_provider_adds_bookmark_list_action_to_center_pane(self) -> None:
        window = SpreadWindow(
            self.pages,
            "bookmark controls",
            processed_pages=list(self.pages),
            cover_single=False,
            auto_prefetch=False,
            settings_path=self.root / "bookmark-controls-settings.json",
            bookmarks_provider=lambda: list(self.bookmarks),
        )
        window.resize(1200, 800)
        try:
            window.show()
            self.application.processEvents()
            window.toggle_reading_info()
            self.application.processEvents()
            self.assertIn("bookmarks", window.reader_action_buttons)
            button = window.reader_action_buttons["bookmarks"][0]
            self.assertIn("Shift+B", button.accessibleDescription())
        finally:
            window.resize_quality_timer.stop()
            window.display_warm_timer.stop()
            window.cache_maintenance_timer.stop()
            window.clear_queued_display_requests()
            window.visible_display_pool.waitForDone(2000)
            window.warm_display_pool.waitForDone(2000)
            window.close()
            window.deleteLater()
            self.application.processEvents()

    def test_accepted_bookmark_uses_one_based_jump_api(self) -> None:
        self.window.index = 0

        def choose_bookmark() -> None:
            modal = QApplication.activeModalWidget()
            self.assertIsInstance(modal, BookmarkDialog)
            modal.go_button.click()

        QTimer.singleShot(0, choose_bookmark)
        self.window.show_bookmarks()
        self.application.processEvents()
        self.assertEqual(self.window.index, 6)

    def test_add_bookmark_false_reports_existing_and_none_remains_success(self) -> None:
        self.window.bookmark_callback = lambda _page_index: False
        self.window.add_bookmark()
        self.assertEqual(
            self.window.statusBar().currentMessage(),
            tr("このページにはしおりがあります。"),
        )

        self.window.bookmark_callback = lambda _page_index: None
        self.window.add_bookmark()
        self.assertEqual(
            self.window.statusBar().currentMessage(),
            tr("しおりを追加しました: p.{page}", page=self.window.index + 1),
        )


if __name__ == "__main__":
    unittest.main()
