from __future__ import annotations

import os
import threading
import time
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
    pages: list[Path] = []
    for index in range(12):
        page = tmp_path / f"page-{index:04d}.png"
        Image.new("RGB", (120, 180), (index * 10, 50, 150)).save(page)
        pages.append(page)

    cleanup_dir = tmp_path / "archive-pages"
    cleanup_dir.mkdir()
    (cleanup_dir / "keep-until-close.txt").write_text("temporary", encoding="utf-8")
    window = SpreadWindow(
        pages,
        "reader lifecycle test",
        cleanup_dir=cleanup_dir,
        processed_pages=[None] * len(pages),
        cover_single=False,
        auto_prefetch=False,
        prefetch_count=2,
        previous_prefetch_count=1,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    window.resize_quality_timer.stop()
    window.prefetch_request_timer.stop()
    yield window, pages, cleanup_dir

    window.resize_quality_timer.stop()
    window.prefetch_request_timer.stop()
    window.display_warm_timer.stop()
    window.cache_maintenance_timer.stop()
    window.clear_queued_display_requests()
    window.visible_display_pool.waitForDone(2000)
    window.warm_display_pool.waitForDone(2000)
    if not window.is_closing:
        window.close()
    window.deleteLater()
    qapp.processEvents()


def _settings() -> dict:
    return {"scale": 2, "noise": 0, "tile": 0, "model": "models-se", "tta": False}


def _drain_events(qapp, predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    qapp.processEvents()
    assert predicate()


def _start_delayed_worker(
    window: SpreadWindow,
    pages: list[Path],
    *,
    generation: int,
    parameter_key: str,
):
    started = threading.Event()
    release = threading.Event()

    def fake_realcugan(source: Path, output: Path, **_settings):
        assert source in pages
        started.set()
        assert release.wait(5)
        output.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image.save(output)
        return SimpleNamespace(returncode=0, output_exists=True)

    patcher = patch.object(viewer_module, "run_realcugan", side_effect=fake_realcugan)
    patcher.start()
    worker = threading.Thread(
        target=window._process_pages_worker,
        args=(_settings(), generation, parameter_key, True),
    )
    worker.start()
    assert started.wait(5)
    return worker, release, patcher


def test_delayed_old_generation_is_ignored_after_navigation_resize_and_quality_change(reader, qapp) -> None:
    window, pages, _cleanup_dir = reader
    old_generation = window.processing_generation
    old_parameter_key = window.current_parameter_key()
    stale_output = window.current_output_path(0)
    window.prefetch_running = True
    window.running_parameter_key = old_parameter_key
    window.prefetch_target_indexes = {0}
    window.active_output_paths = {stale_output}
    window.correction_queue.reset({0: stale_output}, [0])

    worker, release, patcher = _start_delayed_worker(
        window,
        pages,
        generation=old_generation,
        parameter_key=old_parameter_key,
    )
    try:
        window.resize(1000, 700)
        window.move_by(2)
        window.original_check.setChecked(True)
        window.original_check.setChecked(False)
        window.scale_spin.setValue(3)
        assert window.processing_generation == old_generation + 1

        release.set()
        worker.join(5)
        assert not worker.is_alive()
        _drain_events(qapp, lambda: not window.prefetch_running)
    finally:
        release.set()
        worker.join(5)
        patcher.stop()

    assert window.index == 2
    assert not window.original_check.isChecked()
    assert stale_output.is_file()
    assert window.processed_pages[0] is None
    assert window.correction_queue.in_flight is None
    assert window.active_output_paths == set()


def test_close_ignores_delayed_result_and_removes_archive_cleanup(reader, qapp) -> None:
    window, pages, cleanup_dir = reader
    generation = window.processing_generation
    parameter_key = window.current_parameter_key()
    output = window.current_output_path(0)
    window.prefetch_running = True
    window.running_parameter_key = parameter_key
    window.prefetch_target_indexes = {0}
    window.active_output_paths = {output}
    window.correction_queue.reset({0: output}, [0])

    worker, release, patcher = _start_delayed_worker(
        window,
        pages,
        generation=generation,
        parameter_key=parameter_key,
    )
    try:
        window.close()
        assert window.is_closing
        assert not cleanup_dir.exists()

        release.set()
        worker.join(5)
        assert not worker.is_alive()
        _drain_events(qapp, lambda: window.correction_queue.in_flight is None)
    finally:
        release.set()
        worker.join(5)
        patcher.stop()

    assert output.is_file()
    assert window.processed_pages[0] is None
