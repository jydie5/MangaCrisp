from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from mangacrisp_app.reader_widgets import ChoiceButton, ShortcutButton

# The navigation fixture owns the temporary page set and the fairly involved
# SpreadWindow cleanup.  Add the test directory explicitly so this file also
# works when pytest is invoked with only this module as its target.
_TEST_DIR = Path(__file__).resolve().parent
if str(_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_TEST_DIR))

from test_viewer_navigation import ViewerWindowTestCase


class ReaderControlsTests(ViewerWindowTestCase):
    """Regression coverage for the reader's persistent controls and overlay."""

    def _action(self, name: str) -> ShortcutButton:
        actions = self.window.reader_action_buttons[name]
        self.assertTrue(actions, f"reader action {name!r} has no buttons")
        button = actions[0]
        self.assertIsInstance(button, ShortcutButton)
        return button

    def _show_reader(self) -> None:
        self.window.show()
        self.application.processEvents()

    def test_reader_controls_have_stable_action_and_choice_groups(self) -> None:
        self.assertIsInstance(self.window.action_bar, QWidget)

        expected_actions = {
            "previous",
            "next",
            "back_one",
            "forward_one",
            "settings",
            "original",
            "fullscreen",
            "layout",
            "help",
        }
        self.assertTrue(expected_actions.issubset(self.window.reader_action_buttons))
        for name in expected_actions:
            actions = self.window.reader_action_buttons[name]
            self.assertTrue(actions, f"reader action {name!r} has no buttons")
            self.assertTrue(all(isinstance(button, ShortcutButton) for button in actions))

        for name in ("原画", "自然", "クリーニング", "高画質"):
            self.assertIn(name, self.window.preset_buttons)
            self.assertIsInstance(self.window.preset_buttons[name], ChoiceButton)
        self.assertEqual(set(self.window.layout_buttons), {"spread", "single"})
        self.assertTrue(
            all(isinstance(button, QPushButton) for button in self.window.layout_buttons.values())
        )

        self.assertIsInstance(self.window.reading_info_panel, QWidget)
        self.assertFalse(self.window.reading_info_visible)
        self.assertEqual(
            self.window.reading_info_panel.isVisible(), self.window.reading_info_visible
        )

    def test_center_click_opens_overlay_and_blank_click_dismisses_without_navigation(self) -> None:
        self._show_reader()
        self.window.index = 4

        # The last part of the left pane is in the reader's central 20% click
        # zone.  Keep the click away from the persistent action bar and page
        # edges so this exercises the overlay gesture itself.
        QTest.mouseClick(
            self.window.left,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(self.window.left.width() - 10, self.window.left.height() // 2),
        )
        self.application.processEvents()
        self.assertTrue(self.window.reading_info_visible)
        self.assertTrue(self.window.reading_info_panel.isVisible())

        index_before_dismiss = self.window.index
        QTest.mouseClick(
            self.window.left,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(20, 20),
        )
        self.application.processEvents()
        self.assertEqual(self.window.index, index_before_dismiss)
        self.assertFalse(self.window.reading_info_visible)
        self.assertFalse(self.window.reading_info_panel.isVisible())

    def test_overlay_navigation_actions_move_by_spread_and_one_page(self) -> None:
        self._show_reader()
        self.window.index = 4
        self.window.toggle_reading_info()
        self.application.processEvents()
        self.assertTrue(self.window.reading_info_visible)

        self._action("next").click()
        self.assertEqual(self.window.index, 6)
        self._action("previous").click()
        self.assertEqual(self.window.index, 4)
        self._action("forward_one").click()
        self.assertEqual(self.window.index, 5)
        self._action("back_one").click()
        self.assertEqual(self.window.index, 4)

    def test_p_hides_sidebar_but_keeps_persistent_action_bar_visible(self) -> None:
        self._show_reader()
        self.assertTrue(self.window.controls_visible)
        self.assertTrue(self.window.controls_panel.isVisible())
        self.assertTrue(self.window.action_bar.isVisible())

        self.assertTrue(self.window.handle_navigation_key(Qt.Key.Key_P))
        self.application.processEvents()
        self.assertFalse(self.window.controls_visible)
        self.assertFalse(self.window.controls_panel.isVisible())
        self.assertTrue(self.window.action_bar.isVisible())

        # P is a toggle, so the reader can restore the sidebar without
        # reconstructing the action bar.
        self.assertTrue(self.window.handle_navigation_key(Qt.Key.Key_P))
        self.assertTrue(self.window.controls_visible)
        self.assertTrue(self.window.controls_panel.isVisible())
        self.assertTrue(self.window.action_bar.isVisible())

    def test_fullscreen_keeps_persistent_action_bar_visible(self) -> None:
        self._show_reader()
        self.assertFalse(self.window.is_fullscreen)
        self.assertTrue(self.window.action_bar.isVisible())

        self.window.toggle_fullscreen()
        self.application.processEvents()
        self.assertTrue(self.window.is_fullscreen)
        self.assertTrue(self.window.action_bar.isVisible())

        self.window.toggle_fullscreen()
        self.application.processEvents()
        self.assertFalse(self.window.is_fullscreen)
        self.assertTrue(self.window.action_bar.isVisible())

    def test_embedded_fullscreen_keeps_action_bar_visible_in_parent_window(self) -> None:
        host = QWidget()
        host.resize(1000, 760)
        embedded = self.window.__class__(
            self.pages,
            "embedded controls test",
            processed_pages=list(self.pages),
            cover_single=False,
            auto_prefetch=False,
            settings_path=self.root / "embedded-settings.json",
            embedded=True,
            parent=host,
        )
        try:
            host.show()
            embedded.show()
            self.application.processEvents()

            embedded.toggle_fullscreen()
            self.application.processEvents()
            self.assertTrue(embedded.is_fullscreen)
            self.assertTrue(embedded.action_bar.isVisible())

            embedded.toggle_fullscreen()
            self.application.processEvents()
            self.assertFalse(embedded.is_fullscreen)
            self.assertTrue(embedded.action_bar.isVisible())
        finally:
            embedded.close()
            embedded.deleteLater()
            host.close()
            host.deleteLater()
            self.application.processEvents()

    def test_o_and_v_keep_action_button_checked_state_in_sync(self) -> None:
        self._show_reader()
        original_button = self._action("original")
        self.assertTrue(original_button.isCheckable())
        self.assertFalse(original_button.isChecked())
        self.assertFalse(self.window.original_check.isChecked())

        self.assertTrue(self.window.handle_navigation_key(Qt.Key.Key_O))
        self.assertTrue(self.window.original_check.isChecked())
        self.assertTrue(original_button.isChecked())
        self.assertEqual(original_button.isChecked(), self.window.original_check.isChecked())

        self.assertTrue(self.window.handle_navigation_key(Qt.Key.Key_O))
        self.assertFalse(self.window.original_check.isChecked())
        self.assertFalse(original_button.isChecked())

        self.assertEqual(self.window.page_layout_mode, "spread")
        self.assertTrue(self.window.layout_buttons["spread"].isChecked())
        self.assertFalse(self.window.layout_buttons["single"].isChecked())
        self.assertTrue(self.window.handle_navigation_key(Qt.Key.Key_V))
        self.assertEqual(self.window.page_layout_mode, "single")
        self.assertFalse(self.window.layout_buttons["spread"].isChecked())
        self.assertTrue(self.window.layout_buttons["single"].isChecked())
        self.assertTrue(self.window.handle_navigation_key(Qt.Key.Key_V))
        self.assertEqual(self.window.page_layout_mode, "spread")
        self.assertTrue(self.window.layout_buttons["spread"].isChecked())
        self.assertFalse(self.window.layout_buttons["single"].isChecked())

    def test_spinbox_and_combo_popup_arrows_do_not_turn_pages(self) -> None:
        self._show_reader()
        self.window.index = 4
        self.window.apply_settings_mode("manual", persist=False)
        self.application.processEvents()

        self.window.scale_spin.setFocus()
        self.application.processEvents()
        QTest.keyClick(self.window.scale_spin, Qt.Key.Key_Up)
        self.application.processEvents()
        self.assertEqual(self.window.index, 4)

        popup = None
        try:
            self.window.page_layout_combo.setFocus()
            self.window.page_layout_combo.showPopup()
            self.application.processEvents()
            popup = QApplication.activePopupWidget()
            self.assertIsNotNone(popup)
            QTest.keyClick(popup, Qt.Key.Key_Down)
            self.application.processEvents()
            self.assertEqual(self.window.index, 4)
        finally:
            if popup is not None:
                popup.close()
            self.window.page_layout_combo.hidePopup()
            self.application.processEvents()

    def test_escape_dismisses_reading_overlay_before_closing_reader(self) -> None:
        self._show_reader()
        self.window.toggle_reading_info()
        self.assertTrue(self.window.reading_info_visible)
        self.window.setFocus(Qt.FocusReason.OtherFocusReason)
        self.application.processEvents()

        QTest.keyClick(self.window, Qt.Key.Key_Escape)
        self.application.processEvents()

        self.assertFalse(self.window.reading_info_visible)
        self.assertFalse(self.window.reading_info_panel.isVisible())
        self.assertFalse(self.window.is_closing)
        self.assertTrue(self.window.isVisible())

    def test_focused_settings_button_space_activates_without_page_turn(self) -> None:
        self._show_reader()
        self.window.index = 4
        self.assertTrue(self.window.controls_visible)
        settings_button = self._action("settings")
        settings_button.setFocus()
        self.application.processEvents()

        QTest.keyClick(settings_button, Qt.Key.Key_Space)
        self.application.processEvents()

        self.assertEqual(self.window.index, 4)
        self.assertFalse(self.window.controls_visible)
        self.assertFalse(self.window.controls_panel.isVisible())
        self.assertTrue(self.window.action_bar.isVisible())


    def test_escape_from_manual_input_closes_overlay_before_reader(self) -> None:
        self._show_reader()
        self.window.apply_settings_mode('manual', persist=False)
        self.application.processEvents()
        self.window.scale_spin.setFocus()
        self.window.toggle_reading_info()
        QTest.keyClick(self.window.scale_spin, Qt.Key_Escape)
        self.assertFalse(self.window.reading_info_visible)
        self.assertFalse(self.window.is_closing)
