from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image

import mangacrisp_app.viewer as viewer_module
from mangacrisp_app.correction_cache import prune_enhancement_cache
from mangacrisp_app.viewer import SpreadWindow


@pytest.fixture
def reader(tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(viewer_module, "DEFAULT_UPSCALE_DIR", tmp_path / "upscale")
    monkeypatch.setattr(viewer_module, "DISPLAY_CACHE_DIR", tmp_path / "display-cache")
    pages = []
    for index in range(40):
        page = tmp_path / f"{index:04d}.png"
        Image.new("L", (120, 180), index * 4).save(page)
        pages.append(page)

    window = SpreadWindow(
        pages,
        "cache retention test",
        processed_pages=[None] * len(pages),
        cover_single=False,
        auto_prefetch=False,
        prefetch_count=2,
        previous_prefetch_count=1,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
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


def _cache_output(window: SpreadWindow, index: int, color: int = 120) -> Path:
    output_path = window.current_output_path(index)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (120, 180), color).save(output_path)
    window.processed_pages[index] = output_path
    return output_path


def test_distant_backtracking_reuses_retained_png_without_engine(reader) -> None:
    window, _pages, _tmp_path = reader
    distant_path = _cache_output(window, 0)
    _cache_output(window, 30, color=180)

    window.index = 20
    window.maintain_correction_cache()

    assert window.processed_pages[0] is None
    assert window.processed_pages[30] is None
    assert distant_path.is_file()

    window.index = 0
    with patch.object(
        viewer_module,
        "run_realcugan",
        side_effect=AssertionError("engine should not run"),
    ) as engine:
        window.load_cached_outputs([0])

    assert window.processed_pages[0] == distant_path
    engine.assert_not_called()


def test_pruning_releases_external_processed_reference_without_deleting_file(
    reader,
) -> None:
    window, _pages, tmp_path = reader
    external_processed = tmp_path / "external-processed.png"
    Image.new("L", (120, 180), 220).save(external_processed)
    window.processed_pages[0] = external_processed
    window.index = 20

    window.maintain_correction_cache()

    assert window.processed_pages[0] is None
    assert external_processed.is_file()


def test_global_cache_age_and_size_limits_keep_visible_protected_png(
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "upscale"
    protected = cache_root / "interactive" / "current" / "visible.png"
    expired = cache_root / "interactive" / "old" / "expired.png"
    oversized = cache_root / "interactive" / "old" / "lru.png"
    for path in (protected, expired, oversized):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png-cache-data")

    now = time.time()
    old_timestamp = now - 3600
    os.utime(protected, (old_timestamp, old_timestamp))
    os.utime(expired, (old_timestamp, old_timestamp))
    os.utime(oversized, (now, now))

    removed = prune_enhancement_cache(
        cache_root,
        max_bytes=1,
        max_age_seconds=60,
        protected={protected},
        now=now,
    )

    assert removed == 2
    assert protected.is_file()
    assert not expired.exists()
    assert not oversized.exists()


def test_deleted_external_processed_path_is_requeued_for_current_target(reader) -> None:
    window, _pages, tmp_path = reader
    stale_processed = tmp_path / "deleted-processed.png"
    Image.new("L", (120, 180), 80).save(stale_processed)
    stale_processed.unlink()
    window.processed_pages[0] = stale_processed
    window.prefetch_running = True
    window.running_parameter_key = window.current_parameter_key()
    window.prefetch_target_indexes = {0, 1}
    window.correction_queue.clear()
    window.active_output_paths = set()

    with patch.object(
        viewer_module,
        "run_realcugan",
        side_effect=AssertionError("engine should not run"),
    ) as engine:
        window.refresh_correction_queue()

    assert window.processed_pages[0] is None
    assert 0 in window.correction_queue.pending
    assert window.correction_queue.pending[0] == window.current_output_path(0)
    engine.assert_not_called()


@pytest.mark.parametrize("running_flag", ["prefetch_running", "upscale_running"])
def test_running_batch_pruning_protects_active_directory_and_prunes_old_png(
    reader,
    running_flag: str,
) -> None:
    window, _pages, _tmp_path = reader
    active_output = window.current_output_path(0)
    active_output.parent.mkdir(parents=True, exist_ok=True)
    active_output.write_bytes(b"active")
    staging_output = active_output.parent / "staging.png"
    staging_output.write_bytes(b"staging")
    old_output = window.current_output_path(30)
    old_output.parent.mkdir(parents=True, exist_ok=True)
    old_output.write_bytes(b"old")
    now = time.time()
    old_timestamp = now - 3600
    for path in (active_output, staging_output, old_output):
        os.utime(path, (old_timestamp, old_timestamp))

    window.index = 20
    window.processed_pages[0] = active_output
    window.active_output_paths = {active_output}
    setattr(window, running_flag, True)
    window.correction_cache.limit_bytes = 1
    window.correction_cache.max_age_seconds = 60
    window.maintain_correction_cache()

    assert window.processed_pages[0] == active_output
    assert active_output.is_file()
    assert staging_output.is_file()
    assert not old_output.exists()


def test_completed_output_is_released_and_restarts_cache_maintenance(reader) -> None:
    window, _pages, _tmp_path = reader
    output_path = window.current_output_path(0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (120, 180), 160).save(output_path)
    window.active_output_paths = {output_path}
    window.last_disk_cache_prune_signature = ("stale", (0,))
    window.cache_maintenance_timer.stop()

    window.on_upscale_page_done(
        0,
        output_path,
        window.processing_generation,
        window.current_parameter_key(),
    )

    assert output_path not in window.active_output_paths
    assert window.processed_pages[0] == output_path
    assert window.last_disk_cache_prune_signature is None
    assert window.cache_maintenance_timer.isActive()
    window.cache_maintenance_timer.stop()
