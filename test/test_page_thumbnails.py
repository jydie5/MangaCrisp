from __future__ import annotations

import os
import time
import zipfile
from math import inf
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from mangacrisp_app.page_provider import LazyZipPageList, PdfPageList
from mangacrisp_app.page_thumbnails import (
    THUMBNAIL_CACHE_BYTES,
    ThumbnailController,
    ThumbnailSource,
)


def _image(path: Path, color: tuple[int, int, int] = (20, 80, 140)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (120, 180), color).save(path)
    return path


def test_pdf_thumbnail_renders_directly_without_materializing_pdf_page_pngs(tmp_path: Path) -> None:
    pdf_path = tmp_path / "many-pages.pdf"
    images = [Image.new("RGB", (60, 90), (index % 255, 30, 100)) for index in range(300)]
    images[0].save(pdf_path, format="PDF", save_all=True, append_images=images[1:])
    provider = PdfPageList(pdf_path, cache_dir=tmp_path / "pdf-cache")
    source = ThumbnailSource.from_pages(provider)
    image = source.decode(0, QSize(64, 90))
    assert not image.isNull()
    assert provider.extracted == {}
    assert not list(provider.cache_dir.glob("*.png"))


def test_pdf_thumbnail_scale_fits_the_target_and_rejects_invalid_page_sizes() -> None:
    assert ThumbnailSource._pdf_thumbnail_scale((60, 90), QSize(128, 180)) == pytest.approx(2.0)
    assert ThumbnailSource._pdf_thumbnail_scale((100_000, 50_000), QSize(128, 180)) == pytest.approx(0.00128)
    with pytest.raises(RuntimeError):
        ThumbnailSource._pdf_thumbnail_scale((0, 90), QSize(128, 180))
    with pytest.raises(RuntimeError):
        ThumbnailSource._pdf_thumbnail_scale((inf, 90), QSize(128, 180))


def test_image_thumbnail_applies_exif_rotation_and_stays_within_target(tmp_path: Path) -> None:
    source_path = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6  # rotate 90 degrees clockwise
    Image.new("RGB", (300, 100), (20, 80, 140)).save(source_path, exif=exif)
    image = ThumbnailSource.from_pages([source_path]).decode(0, QSize(128, 180))
    assert image.width() <= 128
    assert image.height() <= 180
    assert image.height() > image.width()


def test_zip_thumbnail_decodes_member_without_lazy_provider_materialization(tmp_path: Path) -> None:
    red_path = _image(tmp_path / "red.png", (220, 20, 30))
    blue_path = _image(tmp_path / "blue.png", (30, 40, 220))
    archive_path = tmp_path / "book.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        # Duplicate names are legal ZIP entries and the reader keeps their
        # physical order through ZipInfo rather than a filename lookup.
        archive.write(red_path, "pages/page.png")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.write(blue_path, "pages/page.png")
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
    provider = LazyZipPageList(archive_path, tmp_path / "reader-temp", members)
    source = ThumbnailSource.from_pages(provider)
    first = source.decode(0)
    second = source.decode(1)
    assert first.pixelColor(first.width() // 2, first.height() // 2).red() > 180
    assert second.pixelColor(second.width() // 2, second.height() // 2).blue() > 180
    assert provider.extracted == {}
    assert not provider.temp_dir.exists()


def test_controller_uses_a_bounded_lru_and_drops_stale_worker_results(qapp, tmp_path: Path) -> None:
    pages = [_image(tmp_path / f"{index}.png", (index, 20, 40)) for index in range(8)]
    controller = ThumbnailController(pages)
    ready: list[int] = []
    controller.thumbnail_ready.connect(lambda index, _image, _error: ready.append(index))
    original_decode = ThumbnailSource.decode

    def slow_decode(source, index, size=None):
        time.sleep(0.05)
        return original_decode(source, index, size or QSize(128, 180))

    with patch.object(ThumbnailSource, "decode", slow_decode):
        controller.set_generation(1)
        controller.request([0], 1)
        controller.set_generation(2)
        controller.request([1], 2)
        deadline = time.monotonic() + 3
        while 1 not in ready and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
    assert ready == [1]
    assert 0 not in controller.cache

    for index in range(8):
        controller._remember(index + 100, QImage(1600, 1600, QImage.Format_RGB32))
    assert controller.cache_bytes <= THUMBNAIL_CACHE_BYTES
    assert 100 not in controller.cache
    controller.shutdown()
    controller.pool.waitForDone(5000)


def test_shutdown_discards_an_inflight_result(qapp, tmp_path: Path) -> None:
    controller = ThumbnailController([_image(tmp_path / "page.png")])
    ready: list[int] = []
    controller.thumbnail_ready.connect(lambda index, _image, _error: ready.append(index))
    original_decode = ThumbnailSource.decode

    def slow_decode(source, index, size=None):
        time.sleep(0.05)
        return original_decode(source, index, size or QSize(128, 180))

    with patch.object(ThumbnailSource, "decode", slow_decode):
        controller.set_generation(1)
        controller.request([0], 1)
        controller.shutdown()
        assert controller.pool.waitForDone(5000)
        qapp.processEvents()
    assert ready == []
