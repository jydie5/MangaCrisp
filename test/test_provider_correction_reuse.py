from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

from PIL import Image

from mangacrisp_app.correction_cache import CorrectionDiskCache
from mangacrisp_app.page_provider import PdfPageList, open_zip_pages_for_viewer


def _make_pdf(path: Path) -> None:
    first = Image.new("RGB", (120, 180), (220, 30, 40))
    second = Image.new("RGB", (120, 180), (20, 40, 220))
    first.save(path, format="PDF", save_all=True, append_images=[second])


def _make_zip(path: Path) -> None:
    payload = io.BytesIO()
    Image.new("RGB", (16, 16), (20, 210, 40)).save(payload, format="PNG")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("chapter/001.png", payload.getvalue())


def _write_correction_png(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (12, 12), color).save(path, format="PNG")


def test_pdf_correction_png_is_reused_after_provider_reopen(tmp_path: Path) -> None:
    source = tmp_path / "book.pdf"
    render_cache = tmp_path / "render"
    correction_cache = tmp_path / "upscale"
    _make_pdf(source)

    first_pages = PdfPageList(source, render_cache, dpi=96)
    first_cache = CorrectionDiskCache(correction_cache)
    first_output = first_cache.output_path(first_pages, 0, "se-n0-s2", 2)
    first_output.parent.mkdir(parents=True, exist_ok=True)
    _write_correction_png(first_output, (230, 20, 30))
    assert first_pages.extracted == {}

    reopened_pages = PdfPageList(source, render_cache, dpi=96)
    reopened_cache = CorrectionDiskCache(correction_cache)

    assert reopened_cache.output_path(reopened_pages, 0, "se-n0-s2", 2) == first_output
    assert reopened_cache.cached_path(reopened_pages, 0, "se-n0-s2", 2) == first_output
    with Image.open(first_output) as image:
        assert image.convert("RGB").getpixel((0, 0)) == (230, 20, 30)
    assert reopened_pages.extracted == {}


def test_zip_correction_png_is_reused_after_temp_directory_reopen(tmp_path: Path) -> None:
    source = tmp_path / "book.zip"
    correction_cache = tmp_path / "upscale"
    _make_zip(source)

    first_pages, first_cleanup = open_zip_pages_for_viewer(source)
    second_pages, second_cleanup = open_zip_pages_for_viewer(source)
    try:
        first_cache = CorrectionDiskCache(correction_cache)
        first_output = first_cache.output_path(first_pages, 0, "se-n0-s2", 2)
        first_output.parent.mkdir(parents=True, exist_ok=True)
        _write_correction_png(first_output, (20, 210, 40))
        assert first_pages.extracted == {}

        reopened_cache = CorrectionDiskCache(correction_cache)
        assert reopened_cache.output_path(second_pages, 0, "se-n0-s2", 2) == first_output
        assert reopened_cache.cached_path(second_pages, 0, "se-n0-s2", 2) == first_output
        with Image.open(first_output) as image:
            assert image.convert("RGB").getpixel((0, 0)) == (20, 210, 40)
        assert second_pages.extracted == {}
    finally:
        shutil.rmtree(first_cleanup, ignore_errors=True)
        shutil.rmtree(second_cleanup, ignore_errors=True)
