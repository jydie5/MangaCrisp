from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage, QPixmap

from mangacrisp_app.viewer import SpreadWindow


def _solid_image(color: tuple[int, int, int], size: QSize | None = None) -> QImage:
    image = QImage(size or QSize(12, 12), QImage.Format_RGB888)
    image.fill(QColor(*color))
    return image


def _label_rgb(label) -> tuple[int, int, int]:
    pixmap = label.pixmap()
    assert pixmap is not None and not pixmap.isNull()
    color = pixmap.toImage().pixelColor(0, 0)
    return color.red(), color.green(), color.blue()


@pytest.fixture
def display_window(tmp_path: Path, qapp):
    pages: list[Path] = []
    corrected_pages: list[Path] = []
    for index in range(8):
        page = tmp_path / f"page-{index:04d}.png"
        corrected = tmp_path / f"corrected-{index:04d}.png"
        Image.new("RGB", (120, 180), (20 + index, 40, 180)).save(page)
        Image.new("RGB", (120, 180), (180, 20 + index, 40)).save(corrected)
        pages.append(page)
        corrected_pages.append(corrected)

    window = SpreadWindow(
        pages,
        "display cache lifecycle test",
        processed_pages=corrected_pages,
        cover_single=False,
        auto_prefetch=False,
        settings_path=tmp_path / "settings.json",
    )
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()

    # The constructor renders the first spread asynchronously. Drain that work
    # before building the deterministic cache state used by these tests.
    window.clear_queued_display_requests()
    window.visible_display_pool.waitForDone(2000)
    window.warm_display_pool.waitForDone(2000)
    qapp.processEvents()
    window.display_pixmap_cache.clear()
    window.display_pixmap_cache.capacity = 18
    yield window, pages, corrected_pages, qapp

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


def _spread_keys(window: SpreadWindow, pages: list[Path], corrected_pages: list[Path], start: int):
    keys = []
    for label, index in zip((window.left, window.right), (start, start + 1), strict=True):
        desired = window.display_cache_key(corrected_pages[index], label.size(), True, True)
        fallback = window.display_cache_key(pages[index], label.size(), True, False)
        assert desired is not None
        assert fallback is not None
        window.desired_display_keys[id(label)] = desired
        window.fallback_display_keys[id(label)] = fallback
        keys.append((desired, fallback))
    return keys


def _show_original_spread(window: SpreadWindow, keys) -> None:
    for label, (_desired, fallback) in zip((window.left, window.right), keys, strict=True):
        window.cache_display_pixmap(fallback, QPixmap.fromImage(_solid_image((20, 40, 180))))
        window.show_display_pixmap(label, fallback)


def test_current_spread_keys_survive_warm_completions_and_switch_atomically(display_window) -> None:
    window, pages, corrected_pages, _qapp = display_window
    window.display_pixmap_cache.capacity = 18
    keys = _spread_keys(window, pages, corrected_pages, 0)
    desired = [desired for desired, _fallback in keys]
    fallback = [fallback for _desired, fallback in keys]

    # Leave exactly enough room for the two current fallback images and one
    # first corrected image. The remaining completions model old/warm worker
    # results arriving while the other corrected image is still decoding.
    for index in range(15):
        window.cache_display_pixmap(
            ("old", index, 0, 12, 12, 1, 1),
            QPixmap.fromImage(_solid_image((1, 2, 3))),
        )
    _show_original_spread(window, keys)
    assert len(window.display_pixmap_cache) == 17

    window.on_display_image_done(desired[0], _solid_image((220, 30, 40)), 1)
    assert len(window.display_pixmap_cache) <= 18
    assert desired[0] in window.display_pixmap_cache
    assert desired[1] not in window.display_pixmap_cache

    for index in range(15):
        warm_key = ("warm", index, 0, 12, 12, 1, 1)
        window.on_display_image_done(warm_key, _solid_image((1, 2, 3)), 1)
        assert len(window.display_pixmap_cache) <= 18

    # The second corrected image completes after the warm results. The current
    # desired and fallback keys must all remain resident despite the LRU limit.
    window.on_display_image_done(desired[1], _solid_image((30, 220, 60)), 1)
    assert len(window.display_pixmap_cache) <= 18
    assert all(key in window.display_pixmap_cache for key in desired + fallback)
    assert window.shown_display_keys[id(window.left)] == desired[0]
    assert window.shown_display_keys[id(window.right)] == desired[1]
    assert _label_rgb(window.left) == (220, 30, 40)
    assert _label_rgb(window.right) == (30, 220, 60)


def test_old_spread_keys_can_be_evicted_after_page_move(display_window) -> None:
    window, pages, corrected_pages, qapp = display_window
    keys = _spread_keys(window, pages, corrected_pages, 0)
    old_desired = [desired for desired, _fallback in keys]
    _show_original_spread(window, keys)
    for key, color in zip(old_desired, ((220, 30, 40), (30, 220, 60)), strict=True):
        window.on_display_image_done(key, _solid_image(color), 1)
    assert all(key in window.display_pixmap_cache for key in old_desired)

    # A page move changes the four protected keys. Render the new spread to
    # exercise the same metadata update used by navigation, then discard any
    # queued decode work so only cache eviction is under test below.
    window.index = 2
    window.render_spread(high_quality=True)
    window.display_warm_timer.stop()
    window.cache_maintenance_timer.stop()
    window.clear_queued_display_requests()
    window.visible_display_pool.waitForDone(2000)
    window.warm_display_pool.waitForDone(2000)
    qapp.processEvents()

    assert not any(key in window.desired_display_keys.values() for key in old_desired)
    assert not any(key in window.fallback_display_keys.values() for key in old_desired)

    for index in range(40):
        window.cache_display_pixmap(
            ("after-move", index, 0, 12, 12, 1, 1),
            QPixmap.fromImage(_solid_image((4, 5, 6))),
        )
        assert len(window.display_pixmap_cache) <= 18
        if not any(key in window.display_pixmap_cache for key in old_desired):
            break

    assert not any(key in window.display_pixmap_cache for key in old_desired)
