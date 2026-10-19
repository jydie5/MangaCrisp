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
from mangacrisp_app.correction_queue import pick_next_correction_index
from mangacrisp_app.viewer import (
    SpreadWindow,
    reader_click_action,
    standard_spread_index,
)


class ViewerWindowTestCase(unittest.TestCase):
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


class ViewerNavigationTests(ViewerWindowTestCase):
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

    def test_pro_cache_key_isolated_from_legacy_key_and_se_key_is_unchanged(self) -> None:
        self.assertEqual(
            self.window.current_parameter_key(),
            "scale2_noise0_tile0_models-se",
        )

        self.window.tta_check.setChecked(True)
        self.assertEqual(
            self.window.current_parameter_key(),
            "scale2_noise0_tile0_models-se_tta",
        )

        self.window.tta_check.setChecked(False)
        self.window.model_combo.setCurrentText("models-pro")
        self.window.scale_spin.setValue(3)
        self.window.noise_combo.setCurrentText("3")
        pro_key = self.window.current_parameter_key()
        self.assertEqual(pro_key, "scale3_noise3_tile0_models-pro_syncgap1")
        self.assertNotEqual(pro_key, "scale3_noise3_tile0_models-pro")

        self.window.tta_check.setChecked(True)
        self.assertEqual(
            self.window.current_parameter_key(),
            "scale3_noise3_tile0_models-pro_syncgap1_tta",
        )

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
        self.assertEqual(self.window.index, 5)
        self.assertFalse(self.window.reading_info_visible)

        # The first outside click dismisses the information overlay.  A
        # second click is needed to issue the requested navigation action.
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
        self.window.correction_queue.reset(output_paths, [0, 1, 2])
        with patch("mangacrisp_app.viewer.run_realcugan", side_effect=fake_realcugan):
            self.window._process_pages_worker(
                settings,
                self.window.processing_generation,
                self.window.current_parameter_key(),
                True,
            )

        self.assertEqual(processed_indexes, [2])

    def test_prefetch_worker_serves_current_spread_before_older_lookahead(self) -> None:
        output_paths = {index: self.root / "outputs" / f"{index:04d}.png" for index in (4, 5, 6, 7)}
        self.window.prefetch_target_indexes = {4, 5, 6, 7}
        self.window.correction_queue.reset(output_paths, [4, 5, 6, 7])
        processed_indexes: list[int] = []

        def fake_realcugan(source: Path, output: Path, **_settings):
            index = self.pages.index(source)
            processed_indexes.append(index)
            output.parent.mkdir(parents=True, exist_ok=True)
            Image.open(source).save(output)
            if index == 4:
                # The reader jumps back to pages 0-1 while the lookahead is still running.
                self.window.correction_queue.refresh(
                    {0: self.root / "outputs" / "0000.png", 1: self.root / "outputs" / "0001.png"},
                    [0, 1, 2, 3, 4, 5],
                )
                self.window.prefetch_target_indexes = {0, 1, 2, 3, 4, 5}
            return SimpleNamespace(returncode=0, output_exists=True)

        settings = {"scale": 2, "noise": 0, "tile": 0, "model": "models-se", "tta": False}
        with patch("mangacrisp_app.viewer.run_realcugan", side_effect=fake_realcugan):
            self.window._process_pages_worker(
                settings,
                self.window.processing_generation,
                self.window.current_parameter_key(),
                True,
            )

        self.assertEqual(processed_indexes, [4, 0, 1, 5])

    def test_navigation_during_prefetch_queues_the_visible_spread_first(self) -> None:
        self.window.prefetch_enabled = True
        self.window.prefetch_count_default = 2
        self.window.adaptive_prefetch_count = 2
        with (
            patch("mangacrisp_app.viewer.realcugan_executable", return_value=self.root / "realcugan"),
            patch("mangacrisp_app.viewer.threading.Thread"),
        ):
            self.window.start_prefetch()
            self.assertTrue(self.window.prefetch_running)
            self.assertEqual(self.window.correction_queue.priority[:2], [0, 1])

            self.window.move_by(10)
            self.window.request_prefetch()

        self.assertEqual(self.window.correction_queue.priority[:2], [10, 11])
        self.assertIn(10, self.window.correction_queue.pending)
        self.assertIn(11, self.window.correction_queue.pending)
        self.assertIn(self.window.correction_queue.pending[10], self.window.active_output_paths)

    def test_refresh_does_not_requeue_the_page_being_corrected(self) -> None:
        self.window.prefetch_enabled = True
        self.window.prefetch_count_default = 2
        self.window.adaptive_prefetch_count = 2
        with (
            patch("mangacrisp_app.viewer.realcugan_executable", return_value=self.root / "realcugan"),
            patch("mangacrisp_app.viewer.threading.Thread"),
        ):
            self.window.start_prefetch()
            self.window.prefetch_target_indexes = set(self.window.correction_queue.pending)
            taken = self.window.take_next_correction(True)
            self.assertIsNotNone(taken)
            in_flight = taken[0]
            self.assertEqual(self.window.correction_queue.in_flight, in_flight)
            self.assertNotIn(in_flight, self.window.correction_queue.pending)

            self.window.request_prefetch()

        self.assertNotIn(in_flight, self.window.correction_queue.pending)

    def test_worker_never_corrects_the_same_page_twice_when_requeued_mid_run(self) -> None:
        output_paths = {index: self.root / "outputs" / f"{index:04d}.png" for index in (0, 1)}
        self.window.prefetch_target_indexes = {0, 1}
        self.window.correction_queue.reset(output_paths, [0, 1])
        processed_indexes: list[int] = []

        def fake_realcugan(source: Path, output: Path, **_settings):
            index = self.pages.index(source)
            processed_indexes.append(index)
            # A page turn arrives while this page is still being corrected.
            self.window.refresh_correction_queue()
            output.parent.mkdir(parents=True, exist_ok=True)
            Image.open(source).save(output)
            return SimpleNamespace(returncode=0, output_exists=True)

        settings = {"scale": 2, "noise": 0, "tile": 0, "model": "models-se", "tta": False}
        self.window.running_parameter_key = self.window.current_parameter_key()
        self.window.prefetch_enabled = True
        self.window.adaptive_prefetch_count = 0
        self.window.previous_prefetch_count = 0
        with patch("mangacrisp_app.viewer.run_realcugan", side_effect=fake_realcugan):
            self.window._process_pages_worker(
                settings,
                self.window.processing_generation,
                self.window.current_parameter_key(),
                True,
            )

        self.assertEqual(processed_indexes, [0, 1])

    def test_pick_next_correction_index_follows_priority_and_targets(self) -> None:
        self.assertEqual(pick_next_correction_index([3, 1, 2], {1, 2, 3}), 3)
        self.assertEqual(pick_next_correction_index([3, 1, 2], {1, 2}), 1)
        self.assertEqual(pick_next_correction_index([3, 1, 2], {1, 2, 3}, {2}), 2)
        self.assertIsNone(pick_next_correction_index([3, 1], {2}))
        self.assertIsNone(pick_next_correction_index([], {1}))

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

        self.window.maintain_correction_cache()

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
        for index in range(self.window.display_pixmap_cache.capacity + 10):
            self.window.cache_display_pixmap(("test", index), QPixmap(20, 20))

        self.assertEqual(
            len(self.window.display_pixmap_cache),
            self.window.display_pixmap_cache.capacity,
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


class ReadingInfoBookshelfButtonTests(ViewerWindowTestCase):
    def test_overlay_has_bookshelf_button_that_is_not_a_page_turn(self) -> None:
        self.window.toggle_reading_info()
        button = self.window.reading_info_bookshelf_button
        self.assertTrue(self.window.reading_info_panel.isVisibleTo(self.window))
        self.assertIs(button.parent(), self.window.reading_info_panel)
        self.assertNotIn(button, {self.window.left, self.window.right})

    def test_bookshelf_button_saves_position_and_closes_reader(self) -> None:
        closed: list[SpreadWindow] = []
        saved: list[int] = []
        self.window.close_callback = closed.append
        self.window.page_changed_callback = saved.append
        self.window.move_by(2)
        self.window.notify_page_changed()

        self.window.reading_info_bookshelf_button.click()
        self.application.processEvents()

        self.assertEqual(saved[-1], self.window.index)
        self.assertEqual(closed, [self.window])

    def test_bookshelf_button_leaves_fullscreen_before_closing(self) -> None:
        self.window.close_callback = lambda _window: None
        self.window.toggle_fullscreen()
        self.assertTrue(self.window.is_fullscreen)

        self.window.return_to_bookshelf()
        self.application.processEvents()

        self.assertFalse(self.window.is_fullscreen)
        self.assertTrue(self.window.is_closing)


class CorrectionMissTrackingTests(ViewerWindowTestCase):
    def test_navigation_records_whether_the_spread_was_corrected(self) -> None:
        self.window.prefetch_enabled = True
        self.window.processed_pages = list(self.pages)
        self.window.move_by(2)
        self.assertEqual(list(self.window.correction_misses), [False])

        self.window.processed_pages[4] = None
        self.window.processed_pages[5] = None
        self.window.move_by(2)
        self.assertEqual(list(self.window.correction_misses), [False, True])

    def test_misses_are_bounded_and_raise_the_lead(self) -> None:
        self.window.prefetch_enabled = True
        for index in range(len(self.window.processed_pages)):
            self.window.processed_pages[index] = None
        for _ in range(15):
            self.window.move_by(1)
        self.assertEqual(len(self.window.correction_misses), viewer_module.CORRECTION_MISS_WINDOW)
        self.assertTrue(all(self.window.correction_misses))
        self.assertEqual(viewer_module.correction_lead_factor(self.window.correction_misses), 1.5)

    def test_original_compare_does_not_count_as_a_miss(self) -> None:
        self.window.prefetch_enabled = True
        self.window.original_check.setChecked(True)
        self.window.move_by(2)
        self.assertEqual(list(self.window.correction_misses), [])


class CorrectedDisplayStabilityTests(ViewerWindowTestCase):
    def wait_for_desired_pixmaps(self) -> None:
        for _ in range(200):
            self.application.processEvents()
            keys = [self.window.desired_display_keys.get(id(label)) for label in (self.window.left, self.window.right)]
            if all(key is None or key in self.window.display_pixmap_cache for key in keys) and any(keys):
                self.window.apply_ready_spread_pixmaps()
                return
            time.sleep(0.01)
        self.fail("display pixmaps were not decoded")

    def test_load_cached_outputs_touches_each_file_once_per_session(self) -> None:
        output_path = self.window.current_output_path(0)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.open(self.pages[0]).save(output_path)
        old = time.time() - 3600
        os.utime(output_path, (old, old))

        self.window.load_cached_outputs([0])
        first_mtime = output_path.stat().st_mtime_ns
        self.assertGreater(first_mtime, int(old * 1e9) + 1_000_000)

        time.sleep(0.02)
        self.window.load_cached_outputs([0])

        self.assertEqual(output_path.stat().st_mtime_ns, first_mtime)
        self.assertIs(self.window.processed_pages[0], output_path)

    def test_pro_cache_loader_ignores_legacy_parameter_dir(self) -> None:
        cache_root = self.root / "upscale"
        with patch.object(viewer_module, "DEFAULT_UPSCALE_DIR", cache_root):
            self.window.model_combo.setCurrentText("models-pro")
            self.window.scale_spin.setValue(3)
            self.window.noise_combo.setCurrentText("3")
            self.window.processed_pages = [None] * len(self.window.pages)

            current_path = self.window.current_output_path(0)
            self.assertEqual(
                current_path.parent.parent.name,
                "scale3_noise3_tile0_models-pro_syncgap1",
            )
            legacy_path = (
                cache_root
                / "interactive"
                / "scale3_noise3_tile0_models-pro"
                / current_path.parent.name
                / current_path.name
            )
            self.assertNotEqual(current_path, legacy_path)
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (120, 180), (20, 90, 220)).save(legacy_path)

            self.window.load_cached_outputs([0])
            self.assertIsNone(self.window.processed_pages[0])

            current_path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (120, 180), (220, 90, 20)).save(current_path)
            self.window.load_cached_outputs([0])
            self.assertEqual(self.window.processed_pages[0], current_path)

    def test_display_keys_show_same_image_ignores_size_and_mtime(self) -> None:
        shown = ("a.png", 10, 100, 640, 480, 1, 1)
        self.assertTrue(viewer_module.display_keys_show_same_image(shown, ("a.png", 10, 200, 640, 480, 1, 1)))
        self.assertTrue(viewer_module.display_keys_show_same_image(shown, ("a.png", 11, 200, 640, 480, 0, 1)))
        self.assertFalse(viewer_module.display_keys_show_same_image(shown, ("b.png", 10, 100, 640, 480, 1, 1)))
        self.assertFalse(viewer_module.display_keys_show_same_image(shown, ("a.png", 10, 100, 800, 600, 1, 1)))
        self.assertFalse(viewer_module.display_keys_show_same_image(shown, ("a.png", 10, 100, 640, 480, 1, 0)))
        self.assertFalse(viewer_module.display_keys_show_same_image(None, shown))

    def test_rerender_after_mtime_bump_keeps_the_corrected_pixmap(self) -> None:
        self.window.processed_pages = list(self.pages)
        self.window.processed_pages[0] = self.root / "corrected-0.png"
        self.window.processed_pages[1] = self.root / "corrected-1.png"
        Image.new("L", (120, 180), 200).save(self.window.processed_pages[0])
        Image.new("L", (120, 180), 210).save(self.window.processed_pages[1])
        self.window.show()
        self.window.render_spread(high_quality=True)
        self.wait_for_desired_pixmaps()
        before = [label.pixmap().cacheKey() for label in (self.window.left, self.window.right)]
        corrected_keys = [self.window.desired_display_keys[id(label)] for label in (self.window.left, self.window.right)]
        self.assertTrue(all(key is not None for key in corrected_keys))

        # Simulate a mtime bump on the corrected files: the keys change, the
        # cache misses, and the decode is still pending.
        for label, key in zip((self.window.left, self.window.right), corrected_keys, strict=True):
            bumped = (*key[:2], key[2] + 1, *key[3:])
            self.window.desired_display_keys[id(label)] = bumped
            self.window.fallback_display_keys[id(label)] = self.window.display_cache_key(
                self.pages[self.window.index], label.size(), True, False
            )
        self.window.apply_ready_spread_pixmaps()

        after = [label.pixmap().cacheKey() for label in (self.window.left, self.window.right)]
        self.assertEqual(after, before)
