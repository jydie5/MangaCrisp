from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image

import mangacrisp_app.viewer as viewer_module
from mangacrisp_app.viewer import SpreadWindow


@pytest.fixture
def reader(tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(viewer_module, "DEFAULT_UPSCALE_DIR", tmp_path / "upscale")
    monkeypatch.setattr(viewer_module, "DISPLAY_CACHE_DIR", tmp_path / "display-cache")
    pages = []
    for index in range(24):
        page = tmp_path / f"{index:04d}.png"
        Image.new("L", (120, 180), index * 8).save(page)
        pages.append(page)

    window = SpreadWindow(
        pages,
        "correction recovery test",
        processed_pages=[None] * len(pages),
        cover_single=False,
        auto_prefetch=False,
        prefetch_count=2,
        previous_prefetch_count=1,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.prefetch_enabled = True
    window.prefetch_count_default = 2
    window.adaptive_prefetch_count = 2
    yield window, pages, tmp_path

    window.resize_quality_timer.stop()
    window.prefetch_request_timer.stop()
    window.display_warm_timer.stop()
    window.cache_maintenance_timer.stop()
    window.clear_queued_display_requests()
    window.visible_display_pool.waitForDone(2000)
    window.warm_display_pool.waitForDone(2000)
    window.close()
    window.deleteLater()
    qapp.processEvents()


def _settings() -> dict:
    return {"scale": 2, "noise": 0, "tile": 0, "model": "models-se", "tta": False}


def _queue_prefetch(window: SpreadWindow, indexes: list[int]) -> None:
    window.prefetch_running = True
    window.running_parameter_key = window.current_parameter_key()
    window.prefetch_target_indexes = set(indexes)
    output_paths = {index: window.current_output_path(index) for index in indexes}
    window.correction_queue.reset(output_paths, indexes)
    window.active_output_paths = set(output_paths.values())


def _run_initial_error(window: SpreadWindow, pages: list[Path]) -> list[int]:
    _queue_prefetch(window, [0, 1])
    calls: list[int] = []

    def fake_realcugan(source: Path, output: Path, **_settings):
        index = pages.index(source)
        calls.append(index)
        if index == 0:
            return SimpleNamespace(returncode=1, output_exists=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image.save(output)
        return SimpleNamespace(returncode=0, output_exists=True)

    with patch.object(viewer_module, "run_realcugan", side_effect=fake_realcugan):
        window._process_pages_worker(
            _settings(),
            window.processing_generation,
            window.current_parameter_key(),
            True,
        )
    return calls


def test_prefetch_error_stays_quiet_until_navigation_then_retries(reader) -> None:
    window, pages, tmp_path = reader

    assert _run_initial_error(window, pages) == [0, 1]
    assert window.prefetch_suspended
    window.prefetch_request_timer.stop()

    with patch.object(viewer_module, "realcugan_executable") as executable:
        window.request_prefetch()
        executable.assert_not_called()
        assert not window.prefetch_request_timer.isActive()

        executable.return_value = tmp_path / "realcugan"
        window.move_by(2)

    assert not window.prefetch_suspended
    assert window.prefetch_request_timer.isActive()
    window.prefetch_request_timer.stop()


def test_processing_setting_change_reenables_prefetch_after_error(reader) -> None:
    window, pages, tmp_path = reader

    _run_initial_error(window, pages)
    assert window.prefetch_suspended
    generation = window.processing_generation

    window.on_processing_settings_changed()

    assert window.processing_generation == generation + 1
    assert not window.prefetch_suspended
    with patch.object(
        viewer_module, "realcugan_executable", return_value=tmp_path / "realcugan"
    ) as executable:
        window.request_prefetch()
        executable.assert_called_once_with()
    window.prefetch_request_timer.stop()


def test_fast_resize_navigation_refreshes_visible_correction_queue(reader) -> None:
    window, _pages, tmp_path = reader
    _queue_prefetch(window, [0, 1, 2, 3])
    window.fast_resize_render = True

    with patch.object(
        viewer_module, "realcugan_executable", return_value=tmp_path / "realcugan"
    ):
        window.move_by(10)

    visible = window.visible_page_indexes()
    assert visible == [10, 11]
    assert window.correction_queue.priority[:2] == visible
    assert all(index in window.correction_queue.pending for index in visible)
    assert window.prefetch_request_timer.isActive()
    window.prefetch_request_timer.stop()


def test_prefetch_error_does_not_schedule_idle_retries(reader) -> None:
    window, pages, _tmp_path = reader

    _run_initial_error(window, pages)
    assert window.prefetch_suspended
    window.prefetch_request_timer.stop()

    with patch.object(viewer_module, "realcugan_executable") as executable:
        window.request_prefetch()
        executable.assert_not_called()

    assert not window.prefetch_request_timer.isActive()


def test_provider_failure_completes_batch_without_materializing_again(reader) -> None:
    from unittest.mock import Mock

    window, pages, _tmp_path = reader
    _queue_prefetch(window, [0])

    class BrokenPages(list):
        def __getitem__(self, index):
            raise RuntimeError("page could not be extracted")

    old_signals = window.signals
    window.signals = SimpleNamespace(upscale_page_done=Mock(), upscale_done=Mock())
    window.pages = BrokenPages(pages)
    try:
        window._process_pages_worker(
            _settings(), window.processing_generation, window.current_parameter_key(), True
        )
        window.signals.upscale_done.emit.assert_called_once()
        result = window.signals.upscale_done.emit.call_args.args
        assert result[1] == {}
        assert result[2] == ["Page 1: page could not be extracted"]
        assert window.correction_queue.in_flight is None
    finally:
        window.pages = pages
        window.signals = old_signals
