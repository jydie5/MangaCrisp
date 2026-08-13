from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import mangacrisp_app.viewer as viewer_module
from mangacrisp_app.viewer import (
    SpreadWindow,
    reader_click_action,
    standard_spread_index,
)


class ViewerNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.pages = []
        for index in range(20):
            path = self.root / f"{index:04d}.png"
            Image.new("L", (120, 180), index * 8).save(path)
            self.pages.append(path)
        self.window = SpreadWindow(
            self.pages,
            "navigation test",
            processed_pages=list(self.pages),
            cover_single=False,
            auto_prefetch=False,
            settings_path=self.root / "settings.json",
        )
        self.window.resize(1200, 800)

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

    def test_back_and_forth_does_not_cancel_active_prefetch(self) -> None:
        self.window.prefetch_running = True
        generation = self.window.processing_generation

        for _ in range(10):
            self.window.move_by(2)
            self.window.move_by(-2)

        self.assertEqual(self.window.processing_generation, generation)
        self.assertIn(0, self.window.prefetch_target_indexes)

    def test_h_opens_help_without_shift(self) -> None:
        with patch.object(self.window, "show_shortcuts_help") as show_help:
            handled = self.window.handle_navigation_key(Qt.Key_H)

        self.assertTrue(handled)
        show_help.assert_called_once_with()

    def test_o_toggles_original_and_enhanced_display(self) -> None:
        self.assertFalse(self.window.original_check.isChecked())

        self.assertTrue(self.window.handle_navigation_key(Qt.Key_O))
        self.assertTrue(self.window.original_check.isChecked())

        self.assertTrue(self.window.handle_navigation_key(Qt.Key_O))
        self.assertFalse(self.window.original_check.isChecked())

    def test_click_zones_follow_right_bound_reading_direction(self) -> None:
        self.assertEqual(reader_click_action(100, 1000, "rtl"), "next")
        self.assertEqual(reader_click_action(500, 1000, "rtl"), "info")
        self.assertEqual(reader_click_action(900, 1000, "rtl"), "previous")

    def test_click_zones_follow_left_bound_reading_direction(self) -> None:
        self.assertEqual(reader_click_action(100, 1000, "ltr"), "previous")
        self.assertEqual(reader_click_action(500, 1000, "ltr"), "info")
        self.assertEqual(reader_click_action(900, 1000, "ltr"), "next")

    def test_right_click_always_moves_to_previous_spread(self) -> None:
        for x in (100, 500, 900):
            self.assertEqual(reader_click_action(x, 1000, "rtl", "right"), "previous")
            self.assertEqual(reader_click_action(x, 1000, "ltr", "right"), "previous")

    def test_reader_click_moves_a_spread_or_one_page(self) -> None:
        self.assertTrue(self.window.handle_reader_click("next"))
        self.assertEqual(self.window.index, 2)

        self.assertTrue(self.window.handle_reader_click("previous", one_page=True))
        self.assertEqual(self.window.index, 1)

    def test_single_page_mode_shows_and_moves_one_image_at_a_time(self) -> None:
        self.window.set_page_layout("single")

        self.assertEqual(self.window.visible_page_indexes(), [0])
        self.assertTrue(self.window.right.isHidden())
        self.assertEqual(self.window.page_turn_step(), 1)

        self.assertTrue(self.window.handle_reader_click("next"))
        self.assertEqual(self.window.index, 1)
        self.assertEqual(self.window.visible_page_indexes(), [1])

        self.assertTrue(self.window.handle_navigation_key(Qt.Key_Left))
        self.assertEqual(self.window.index, 2)

    def test_v_toggles_single_page_and_spread_modes(self) -> None:
        self.window.index = 5

        self.assertTrue(self.window.handle_navigation_key(Qt.Key_V))
        self.assertEqual(self.window.page_layout_mode, "single")
        self.assertEqual(self.window.index, 5)

        self.assertTrue(self.window.handle_navigation_key(Qt.Key_V))
        self.assertEqual(self.window.page_layout_mode, "spread")
        self.assertEqual(self.window.index, 4)
        self.assertFalse(self.window.right.isHidden())

    def test_standard_spread_index_contains_current_page(self) -> None:
        self.assertEqual(standard_spread_index(5, cover_single=False), 4)
        self.assertEqual(standard_spread_index(6, cover_single=False), 6)
        self.assertEqual(standard_spread_index(2, cover_single=True), 1)
        self.assertEqual(standard_spread_index(3, cover_single=True), 3)

    def test_center_click_toggles_reading_info(self) -> None:
        self.assertFalse(self.window.reading_info_visible)

        self.assertTrue(self.window.handle_reader_click("info"))
        self.assertTrue(self.window.reading_info_visible)

        self.assertTrue(self.window.handle_reader_click("info"))
        self.assertFalse(self.window.reading_info_visible)

    def test_qt_mouse_clicks_navigate_and_toggle_info(self) -> None:
        self.window.show()
        self.application.processEvents()
        self.window.index = 4

        QTest.mouseClick(
            self.window.left,
            Qt.LeftButton,
            Qt.NoModifier,
            QPoint(20, self.window.left.height() // 2),
        )
        self.assertEqual(self.window.index, 6)

        QTest.mouseClick(
            self.window.right,
            Qt.LeftButton,
            Qt.NoModifier,
            QPoint(self.window.right.width() - 20, self.window.right.height() // 2),
        )
        self.assertEqual(self.window.index, 4)

        QTest.mouseClick(
            self.window.left,
            Qt.LeftButton,
            Qt.ShiftModifier,
            QPoint(20, self.window.left.height() // 2),
        )
        self.assertEqual(self.window.index, 5)

        QTest.mouseClick(
            self.window.left,
            Qt.LeftButton,
            Qt.NoModifier,
            QPoint(self.window.left.width() - 10, self.window.left.height() // 2),
        )
        self.assertTrue(self.window.reading_info_visible)

        QTest.mouseClick(
            self.window.left,
            Qt.RightButton,
            Qt.NoModifier,
            QPoint(20, self.window.left.height() // 2),
        )
        self.assertEqual(self.window.index, 3)

    def test_prefetch_worker_skips_pages_outside_latest_target(self) -> None:
        output_paths = {
            index: self.root / "outputs" / f"{index:04d}.png"
            for index in range(3)
        }
        self.window.prefetch_target_indexes = {2}
        processed_indexes: list[int] = []

        def fake_realcugan(source: Path, output: Path, **_settings):
            index = self.pages.index(source)
            processed_indexes.append(index)
            output.parent.mkdir(parents=True, exist_ok=True)
            Image.open(source).save(output)
            return SimpleNamespace(returncode=0, output_exists=True)

        settings = {"scale": 2, "noise": 0, "tile": 0, "model": "models-se", "tta": False}
        with patch("mangacrisp_app.viewer.run_realcugan", side_effect=fake_realcugan):
            self.window._process_pages_worker(
                [0, 1, 2],
                output_paths,
                settings,
                self.window.processing_generation,
                self.window.current_parameter_key(),
                True,
            )

        self.assertEqual(processed_indexes, [2])

    def test_prefetch_tracks_active_outputs_before_worker_starts(self) -> None:
        self.window.prefetch_enabled = True
        self.window.prefetch_count_default = 2
        self.window.adaptive_prefetch_count = 2

        with (
            patch("mangacrisp_app.viewer.realcugan_executable", return_value=self.root / "realcugan"),
            patch("mangacrisp_app.viewer.threading.Thread") as thread,
        ):
            self.window.start_prefetch()

        self.assertTrue(self.window.prefetch_running)
        self.assertTrue(self.window.active_output_paths)
        thread.return_value.start.assert_called_once()

    def test_cache_pruning_never_deletes_external_processed_images(self) -> None:
        external_output = self.root / "external-processed.png"
        Image.new("L", (120, 180), 255).save(external_output)
        self.window.index = 15
        self.window.processed_pages[0] = external_output

        self.window.prune_revolving_correction_cache()

        self.assertTrue(external_output.exists())
        self.assertIsNone(self.window.processed_pages[0])

    def test_slow_image_decode_does_not_block_page_navigation(self) -> None:
        self.window.clear_queued_display_requests()
        self.window.visible_display_pool.waitForDone(1000)
        self.window.warm_display_pool.waitForDone(1000)
        self.application.processEvents()
        self.window.display_pixmap_cache.clear()
        self.window.resize_quality_timer.stop()
        self.window.fast_resize_render = False
        original_decode = viewer_module.decode_scaled_display_image

        def slow_decode(*args, **kwargs):
            time.sleep(0.25)
            return original_decode(*args, **kwargs)

        with patch("mangacrisp_app.viewer.decode_scaled_display_image", side_effect=slow_decode):
            started = time.perf_counter()
            self.window.move_by(2)
            navigation_seconds = time.perf_counter() - started
            self.assertLess(navigation_seconds, 0.1)
            self.window.visible_display_pool.waitForDone(2000)
            self.application.processEvents()

        self.assertIsNotNone(self.window.left.pixmap())
        self.assertFalse(self.window.left.pixmap().isNull())
        self.assertIsNotNone(self.window.right.pixmap())
        self.assertFalse(self.window.right.pixmap().isNull())

    def test_spread_is_revealed_only_after_both_async_images_are_ready(self) -> None:
        self.window.clear_queued_display_requests()
        self.window.visible_display_pool.waitForDone(1000)
        self.window.warm_display_pool.waitForDone(1000)
        self.application.processEvents()
        self.window.display_pixmap_cache.clear()
        self.window.resize_quality_timer.stop()
        self.window.fast_resize_render = False
        original_decode = viewer_module.decode_scaled_display_image
        decode_count = 0

        def uneven_decode(*args, **kwargs):
            nonlocal decode_count
            decode_count += 1
            time.sleep(0.05 if decode_count == 1 else 0.3)
            return original_decode(*args, **kwargs)

        with patch("mangacrisp_app.viewer.decode_scaled_display_image", side_effect=uneven_decode):
            self.window.move_by(2)
            self.window.display_warm_timer.stop()
            self.window.cache_maintenance_timer.stop()
            deadline = time.perf_counter() + 0.15
            while time.perf_counter() < deadline:
                self.application.processEvents()
                time.sleep(0.01)
            self.assertTrue(self.window.left.pixmap() is None or self.window.left.pixmap().isNull())
            self.assertTrue(self.window.right.pixmap() is None or self.window.right.pixmap().isNull())
            self.window.visible_display_pool.waitForDone(2000)
            deadline = time.perf_counter() + 0.2
            while time.perf_counter() < deadline:
                self.application.processEvents()
                if (
                    self.window.left.pixmap() is not None
                    and not self.window.left.pixmap().isNull()
                    and self.window.right.pixmap() is not None
                    and not self.window.right.pixmap().isNull()
                ):
                    break
                time.sleep(0.01)

        self.assertFalse(self.window.left.pixmap().isNull())
        self.assertFalse(self.window.right.pixmap().isNull())

    def test_original_fallback_is_visible_while_corrected_images_decode(self) -> None:
        corrected_pages = []
        for index, source in enumerate(self.pages):
            corrected = self.root / f"corrected-{index:04d}.png"
            Image.open(source).save(corrected)
            corrected_pages.append(corrected)
        self.window.processed_pages = corrected_pages
        self.window.clear_queued_display_requests()
        self.window.visible_display_pool.waitForDone(1000)
        self.window.warm_display_pool.waitForDone(1000)
        self.application.processEvents()
        self.window.display_pixmap_cache.clear()
        self.window.resize_quality_timer.stop()
        self.window.fast_resize_render = False
        original_decode = viewer_module.decode_scaled_display_image
        release_corrected = threading.Event()

        def corrected_is_slow(*args, **kwargs):
            normalize_color = bool(args[4])
            if normalize_color:
                release_corrected.wait(timeout=2)
            return original_decode(*args, **kwargs)

        with patch("mangacrisp_app.viewer.decode_scaled_display_image", side_effect=corrected_is_slow):
            try:
                self.window.move_by(2)
                self.window.display_warm_timer.stop()
                self.window.cache_maintenance_timer.stop()
                deadline = time.perf_counter() + 1
                while time.perf_counter() < deadline:
                    self.application.processEvents()
                    if (
                        self.window.left.pixmap() is not None
                        and not self.window.left.pixmap().isNull()
                        and self.window.right.pixmap() is not None
                        and not self.window.right.pixmap().isNull()
                    ):
                        break
                    time.sleep(0.005)

                self.assertFalse(self.window.left.pixmap().isNull())
                self.assertFalse(self.window.right.pixmap().isNull())
                desired_keys = [
                    self.window.desired_display_keys[id(self.window.left)],
                    self.window.desired_display_keys[id(self.window.right)],
                ]
                self.assertTrue(any(key not in self.window.display_pixmap_cache for key in desired_keys))
            finally:
                release_corrected.set()

            self.window.visible_display_pool.waitForDone(2000)
            self.application.processEvents()

        self.assertTrue(all(key in self.window.display_pixmap_cache for key in desired_keys))
        self.assertFalse(self.window.left.pixmap().isNull())
        self.assertFalse(self.window.right.pixmap().isNull())

    def test_corrected_color_page_preserves_rgb_channels(self) -> None:
        corrected = self.root / "corrected-color.png"
        Image.new("RGB", (120, 180), (20, 90, 220)).save(corrected)

        image = viewer_module.decode_scaled_display_image(
            corrected,
            120,
            180,
            True,
            True,
        )

        self.assertFalse(image.isNull())
        self.assertEqual(image.format(), QImage.Format_RGB888)
        pixel = image.pixelColor(60, 90)
        self.assertEqual((pixel.red(), pixel.green(), pixel.blue()), (20, 90, 220))

    def test_corrected_page_ignores_legacy_grayscale_display_cache(self) -> None:
        corrected = self.root / "corrected-color.png"
        Image.new("RGB", (120, 180), (20, 90, 220)).save(corrected)
        self.window.processed_pages[0] = corrected

        with (
            patch.object(viewer_module, "DISPLAY_CACHE_DIR", self.root / "display-cache"),
            patch.object(self.window, "visible_spread_uses_original", return_value=False),
        ):
            legacy_cache = viewer_module.display_cache_path_for(corrected)
            self.assertIsNotNone(legacy_cache)
            legacy_cache.parent.mkdir(parents=True, exist_ok=True)
            Image.new("L", (120, 180), 100).save(legacy_cache)
            display_path, normalize_color = self.window.display_source_for_index(0)

        self.assertEqual(display_path, corrected)
        self.assertTrue(normalize_color)

    def test_legacy_grayscale_display_cache_is_removed(self) -> None:
        display_cache = self.root / "display-cache"
        display_cache.mkdir()
        Image.new("L", (120, 180), 100).save(display_cache / "legacy.png")

        with patch.object(viewer_module, "DISPLAY_CACHE_DIR", display_cache):
            viewer_module.remove_legacy_display_cache()

        self.assertFalse(display_cache.exists())

    def test_display_cache_remains_bounded(self) -> None:
        for index in range(self.window.display_pixmap_cache_limit + 10):
            self.window.cache_display_pixmap(("test", index), QPixmap(20, 20))

        self.assertEqual(
            len(self.window.display_pixmap_cache),
            self.window.display_pixmap_cache_limit,
        )

    def test_window_close_does_not_wait_for_active_decode(self) -> None:
        self.window.clear_queued_display_requests()
        self.window.visible_display_pool.waitForDone(1000)
        self.application.processEvents()
        self.window.display_pixmap_cache.clear()
        original_decode = viewer_module.decode_scaled_display_image

        def slow_decode(*args, **kwargs):
            time.sleep(0.5)
            return original_decode(*args, **kwargs)

        with patch("mangacrisp_app.viewer.decode_scaled_display_image", side_effect=slow_decode):
            self.window.move_by(2)
            started = time.perf_counter()
            self.window.close()
            close_seconds = time.perf_counter() - started

        self.assertLess(close_seconds, 0.1)

    def test_reading_position_save_is_debounced_outside_navigation(self) -> None:
        saved_indexes: list[int] = []
        self.window.page_changed_callback = saved_indexes.append

        self.window.move_by(2)
        self.window.move_by(2)

        self.assertEqual(saved_indexes, [])
        deadline = time.perf_counter() + 0.45
        while time.perf_counter() < deadline:
            self.application.processEvents()
            time.sleep(0.01)
        self.assertEqual(saved_indexes, [4])

    def test_rapid_direction_reversals_stay_under_100ms(self) -> None:
        self.window.clear_queued_display_requests()
        self.window.visible_display_pool.waitForDone(1000)
        self.window.warm_display_pool.waitForDone(1000)
        self.window.display_pixmap_cache.clear()
        self.window.resize_quality_timer.stop()
        self.window.fast_resize_render = False
        original_decode = viewer_module.decode_scaled_display_image
        durations = []

        def slow_decode(*args, **kwargs):
            time.sleep(0.2)
            return original_decode(*args, **kwargs)

        with patch("mangacrisp_app.viewer.decode_scaled_display_image", side_effect=slow_decode):
            for iteration in range(40):
                started = time.perf_counter()
                self.window.move_by(2 if iteration % 2 == 0 else -2)
                durations.append(time.perf_counter() - started)

        self.assertLess(max(durations), 0.1)


if __name__ == "__main__":
    unittest.main()
