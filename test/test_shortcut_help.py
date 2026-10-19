from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QLabel,
    QMainWindow,
    QScrollArea,
    QTextBrowser,
    QWidget,
)

from mangacrisp_app.branding import PROJECT_URL, SUPPORT_URL
from mangacrisp_app.i18n import set_language
from mangacrisp_app.shortcut_help import ShortcutHelpDialog
from mangacrisp_app.viewer import show_help_dialog, viewer_shortcuts_text

_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

from test_viewer_navigation import ViewerWindowTestCase

HELP_TEXT = "← / Space: next\n→: previous\nEsc: close this help"


class ShortcutHelpDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.parent = QMainWindow()
        self.parent.resize(900, 620)
        self.parent.show()
        self.application.processEvents()
        self.dialog = ShortcutHelpDialog(self.parent, HELP_TEXT)
        self.dialog.setModal(True)
        self.dialog.show()
        self.application.processEvents()

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        self.parent.close()
        self.parent.deleteLater()
        self.application.processEvents()

    def _outside_point(self, dialog: QDialog) -> QPoint:
        card = dialog.card
        for point in (
            QPoint(8, 8),
            QPoint(dialog.width() - 9, 8),
            QPoint(8, dialog.height() - 9),
            QPoint(dialog.width() - 9, dialog.height() - 9),
        ):
            if not card.geometry().contains(point):
                return point
        self.fail("help card covers every backdrop corner")

    def _card_blank_point(self) -> QPoint:
        card = self.dialog.card
        for y in range(6, max(6, card.height() - 6), 8):
            for x in range(6, max(6, card.width() - 6), 8):
                point = QPoint(x, y)
                if card.childAt(point) is None:
                    return point
        self.fail("help card has no blank click target")

    def test_backdrop_has_visible_alpha_for_native_hit_testing(self) -> None:
        pixel = self.dialog.grab().toImage().pixelColor(8, 8)
        self.assertGreater(pixel.alpha(), 0)
        self.assertLess(pixel.alpha(), 255)

    def test_dialog_covers_parent_and_centers_card(self) -> None:
        self.assertTrue(self.dialog.isModal())
        self.assertEqual(self.dialog.size(), self.parent.size())
        self.assertEqual(
            self.dialog.mapToGlobal(self.dialog.rect().center()),
            self.parent.mapToGlobal(self.parent.rect().center()),
        )
        self.assertIsInstance(self.dialog.card, QWidget)
        self.assertLess(self.dialog.card.width(), self.dialog.width())
        self.assertLess(self.dialog.card.height(), self.dialog.height())
        self.assertAlmostEqual(
            self.dialog.card.geometry().center().x(),
            self.dialog.rect().center().x(),
            delta=4,
        )
        self.assertAlmostEqual(
            self.dialog.card.geometry().center().y(),
            self.dialog.rect().center().y(),
            delta=4,
        )

    def test_outside_press_does_not_close_until_matching_release(self) -> None:
        point = self._outside_point(self.dialog)

        for button in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            with self.subTest(button=button):
                self.dialog.show()
                self.application.processEvents()
                QTest.mousePress(self.dialog, button, pos=point)
                self.application.processEvents()
                self.assertTrue(self.dialog.isVisible())

                QTest.mouseRelease(self.dialog, button, pos=point)
                self.application.processEvents()
                self.assertFalse(self.dialog.isVisible())

    def test_inside_card_blank_click_does_not_dismiss(self) -> None:
        point = self._card_blank_point()
        QTest.mouseClick(self.dialog.card, Qt.MouseButton.LeftButton, pos=point)
        self.application.processEvents()
        self.assertTrue(self.dialog.isVisible())

    def test_escape_closes_from_button_and_scroll_focus(self) -> None:
        focus_targets = [self.dialog.close_button]
        focus_targets.extend(self.dialog.findChildren(QScrollArea))
        focus_targets.extend(self.dialog.findChildren(QTextBrowser))
        focus_targets.append(self.dialog.project_links)
        self.assertTrue(focus_targets)

        for target in focus_targets:
            with self.subTest(target=type(target).__name__):
                self.dialog.show()
                self.application.processEvents()
                target.setFocus(Qt.FocusReason.OtherFocusReason)
                QTest.keyClick(target, Qt.Key.Key_Escape)
                self.application.processEvents()
                self.assertFalse(self.dialog.isVisible())

    def test_close_button_closes_dialog(self) -> None:
        self.assertTrue(self.dialog.close_button.isEnabled())
        self.dialog.close_button.click()
        self.application.processEvents()
        self.assertFalse(self.dialog.isVisible())

    def test_project_links_are_present_and_accessible(self) -> None:
        visible_markup: list[str] = []
        link_capable = False
        for label in self.dialog.findChildren(QLabel):
            if label.isVisible():
                visible_markup.append(label.text())
                link_capable |= bool(
                    label.textInteractionFlags()
                    & Qt.TextInteractionFlag.LinksAccessibleByMouse
                )
        for browser in self.dialog.findChildren(QTextBrowser):
            if browser.isVisible():
                visible_markup.append(browser.toHtml())
                link_capable = True
        for button in self.dialog.findChildren(QAbstractButton):
            if button.isVisible():
                visible_markup.extend((button.text(), button.accessibleName()))

        markup = "\n".join(visible_markup)
        self.assertIn(PROJECT_URL, markup)
        self.assertIn(SUPPORT_URL, markup)
        self.assertTrue(link_capable)
        self.assertTrue(
            self.dialog.close_button.accessibleName() or self.dialog.close_button.text()
        )

    def test_long_help_fits_900_by_620_in_both_languages(self) -> None:
        for language in ("ja", "en"):
            with self.subTest(language=language):
                set_language(language)
                dialog = ShortcutHelpDialog(self.parent, viewer_shortcuts_text("rtl"))
                dialog.setModal(True)
                dialog.resize(900, 620)
                dialog.show()
                self.application.processEvents()
                self.assertLessEqual(dialog.width(), 900)
                self.assertLessEqual(dialog.height(), 620)
                self.assertGreater(dialog.card.width(), 0)
                self.assertGreater(dialog.card.height(), 0)
                self.assertGreaterEqual(dialog.card.geometry().left(), 0)
                self.assertGreaterEqual(dialog.card.geometry().top(), 0)
                self.assertLessEqual(
                    dialog.card.geometry().right(), dialog.rect().right()
                )
                self.assertLessEqual(
                    dialog.card.geometry().bottom(), dialog.rect().bottom()
                )
                self.assertIsInstance(dialog.scroll, QScrollArea)
                self.assertIsNotNone(dialog.scroll.widget())
                dialog.close()
                dialog.deleteLater()
                self.application.processEvents()
        set_language("en")


class ShortcutHelpViewerIntegrationTests(ViewerWindowTestCase):
    def _run_help_with(self, callback) -> list[QDialog | None]:
        seen: list[QDialog | None] = []

        def run_callback() -> None:
            modal = QApplication.activeModalWidget()
            seen.append(modal if isinstance(modal, QDialog) else None)
            if modal is not None:
                callback(modal)

        QTimer.singleShot(0, run_callback)
        show_help_dialog(
            self.window, viewer_shortcuts_text(self.window.reading_direction)
        )
        self.application.processEvents()
        return seen

    def test_escape_does_not_exit_fullscreen_or_close_reader(self) -> None:
        self.window.show()
        self.application.processEvents()
        self.window.index = 4
        self.window.toggle_fullscreen()
        self.application.processEvents()

        seen = self._run_help_with(
            lambda modal: (
                modal.close_button.setFocus(Qt.FocusReason.OtherFocusReason),
                QTest.keyClick(modal.close_button, Qt.Key.Key_Escape),
            )
        )

        self.assertEqual(len(seen), 1)
        self.assertIsNotNone(seen[0])
        self.assertEqual(self.window.index, 4)
        self.assertTrue(self.window.is_fullscreen)
        self.assertFalse(self.window.is_closing)
        self.window.toggle_fullscreen()

    def test_outside_click_closes_help_without_turning_reader_page(self) -> None:
        self.window.show()
        self.application.processEvents()
        self.window.index = 4
        before = self.window.index
        pressed_visible: list[bool] = []

        def dismiss_outside(modal: QDialog) -> None:
            point = self._outside_point(modal)
            QTest.mousePress(modal, Qt.MouseButton.LeftButton, pos=point)
            self.application.processEvents()
            pressed_visible.append(modal.isVisible())
            QTest.mouseRelease(modal, Qt.MouseButton.LeftButton, pos=point)

        seen = self._run_help_with(dismiss_outside)

        self.assertEqual(len(seen), 1)
        self.assertIsNotNone(seen[0])
        self.assertEqual(pressed_visible, [True])
        self.assertEqual(self.window.index, before)
        self.assertFalse(self.window.is_closing)

    def _outside_point(self, dialog: QDialog) -> QPoint:
        card = dialog.card
        for point in (
            QPoint(8, 8),
            QPoint(dialog.width() - 9, 8),
            QPoint(8, dialog.height() - 9),
            QPoint(dialog.width() - 9, dialog.height() - 9),
        ):
            if not card.geometry().contains(point):
                return point
        self.fail("help card covers every backdrop corner")


if __name__ == "__main__":
    unittest.main()
