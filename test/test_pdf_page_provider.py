import io
import os
import shutil
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from mangacrisp_app import page_provider
from mangacrisp_app.page_provider import (
    PDF_RENDER_DPI,
    LazyZipPageList,
    PdfPageList,
    open_pages_for_viewer,
    open_zip_pages_for_viewer,
    pdf_page_count,
    pdf_render_cache_dir,
    pdf_source_key,
    prune_render_cache,
)


def make_color_pdf(path: Path, colors: list[tuple[int, int, int]]) -> None:
    pages = [Image.new("RGB", (120, 180), color) for color in colors]
    pages[0].save(path, format="PDF", save_all=True, append_images=pages[1:])


def test_pdf_pages_render_lazily_and_preserve_color(tmp_path: Path) -> None:
    source = tmp_path / "color.pdf"
    cache = tmp_path / "cache"
    make_color_pdf(source, [(230, 20, 30), (20, 210, 40), (30, 40, 220)])

    pages = PdfPageList(source, cache, dpi=96)

    assert len(pages) == 3
    assert list(cache.rglob("*.png")) == []

    rendered = pages[1]
    assert rendered.is_file()
    assert len(list(cache.rglob("*.png"))) == 1
    with Image.open(rendered) as image:
        red, green, blue = image.convert("RGB").getpixel((image.width // 2, image.height // 2))
    assert green > 180
    assert red < 80
    assert blue < 80


def test_open_pages_for_viewer_uses_pdf_page_source(tmp_path: Path) -> None:
    source = tmp_path / "book.pdf"
    make_color_pdf(source, [(255, 255, 255), (0, 0, 0)])

    pages, cleanup = open_pages_for_viewer(source)

    assert isinstance(pages, PdfPageList)
    assert len(pages) == 2
    assert cleanup is None
    assert pdf_page_count(source) == 2


def test_prune_render_cache_removes_oldest_unprotected_files(tmp_path: Path) -> None:
    old = tmp_path / "a" / "old.png"
    protected = tmp_path / "b" / "protected.png"
    newest = tmp_path / "c" / "new.png"
    for path in (old, protected, newest):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 10)
    old.touch()
    protected.touch()
    newest.touch()
    old_mtime = 1_000_000_000
    protected_mtime = old_mtime + 1
    newest_mtime = old_mtime + 2
    import os

    os.utime(old, (old_mtime, old_mtime))
    os.utime(protected, (protected_mtime, protected_mtime))
    os.utime(newest, (newest_mtime, newest_mtime))

    removed = prune_render_cache(tmp_path, max_bytes=10, protected={protected})

    assert removed == 2
    assert not old.exists()
    assert protected.exists()
    assert not newest.exists()


def test_300_page_pdf_does_not_render_until_a_page_is_requested(tmp_path: Path) -> None:
    source = tmp_path / "large.pdf"
    cache = tmp_path / "cache"
    make_color_pdf(source, [(index % 255, 80, 160) for index in range(300)])

    pages = PdfPageList(source, cache, dpi=72)

    assert len(pages) == 300
    assert list(cache.rglob("*.png")) == []
    assert pages[0].is_file()
    assert pages[150].is_file()
    assert pages[299].is_file()
    assert len(list(cache.rglob("*.png"))) == 3


def test_pdf_cache_source_identity_is_stable_across_reopen_and_touch(tmp_path: Path) -> None:
    source = tmp_path / "stable.pdf"
    cache = tmp_path / "cache"
    make_color_pdf(source, [(230, 20, 30), (20, 210, 40)])

    first = PdfPageList(source, cache, dpi=96)
    first_identity = first.cache_source_identity(0)
    rendered = first[0]
    first_mtime = rendered.stat().st_mtime_ns

    # Repeated viewer lookups in one session must not keep changing the
    # rendered PNG mtime and therefore must not churn display cache keys.
    time.sleep(0.003)
    assert first[0] == rendered
    assert rendered.stat().st_mtime_ns == first_mtime

    time.sleep(0.003)
    second = PdfPageList(source, cache, dpi=96)
    assert second.cache_source_identity(0) == first_identity
    assert second[0] == rendered
    reopened_mtime = rendered.stat().st_mtime_ns
    assert reopened_mtime >= first_mtime
    time.sleep(0.003)
    assert second[0] == rendered
    assert rendered.stat().st_mtime_ns == reopened_mtime


def test_pdf_materialize_renders_again_when_cached_file_disappears(tmp_path: Path) -> None:
    source = tmp_path / "recreate.pdf"
    cache = tmp_path / "cache"
    make_color_pdf(source, [(230, 20, 30)])

    pages = PdfPageList(source, cache, dpi=96)
    rendered = pages[0]
    rendered.unlink()

    recreated = pages[0]

    assert recreated == rendered
    assert recreated.is_file()
    with Image.open(recreated) as image:
        assert image.convert("RGB").getpixel((image.width // 2, image.height // 2))[0] > 150


def test_pdf_cache_source_identity_changes_when_source_changes(tmp_path: Path) -> None:
    source = tmp_path / "changing.pdf"
    cache = tmp_path / "cache"
    make_color_pdf(source, [(230, 20, 30)])

    first = PdfPageList(source, cache, dpi=96)
    first_identity = first.cache_source_identity(0)
    first_path = first.cache_dir

    make_color_pdf(source, [(20, 210, 40)])
    source_stat = source.stat()
    os.utime(
        source,
        ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns + 1_000_000_000),
    )
    assert first.cache_source_identity(0) == first_identity
    second = PdfPageList(source, cache, dpi=96)

    assert second.cache_source_identity(0) != first_identity
    assert second.cache_dir != first_path


def test_pdf_render_cache_keeps_default_path_and_separates_non_default_dpi(tmp_path: Path) -> None:
    source = tmp_path / "dpi.pdf"
    cache = tmp_path / "cache"
    make_color_pdf(source, [(230, 20, 30)])
    fingerprint = pdf_source_key(source)

    default = PdfPageList(source, cache, dpi=PDF_RENDER_DPI)
    low_dpi = PdfPageList(source, cache, dpi=96)

    assert default.cache_dir == cache / fingerprint
    assert low_dpi.cache_dir == cache / fingerprint / "dpi-96"
    assert default.cache_dir != low_dpi.cache_dir
    assert default.cache_source_identity(0) != low_dpi.cache_source_identity(0)
    assert pdf_render_cache_dir(source, cache, dpi=PDF_RENDER_DPI) == default.cache_dir
    assert pdf_render_cache_dir(source, cache, dpi=96) == low_dpi.cache_dir

    # A pruner or cache clear can remove the directory after construction;
    # the next render must recreate its parent before writing the temp PNG.
    shutil.rmtree(low_dpi.cache_dir)
    rendered = low_dpi[0]
    assert rendered.is_file()
    assert rendered.parent == low_dpi.cache_dir


def test_zip_cache_source_identity_ignores_recreated_temp_directory(tmp_path: Path) -> None:
    archive_path = tmp_path / "book.zip"
    image = io.BytesIO()
    Image.new("RGB", (16, 16), (20, 210, 40)).save(image, format="PNG")
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("chapter/001.png", image.getvalue())

    first, first_cleanup = open_zip_pages_for_viewer(archive_path)
    second, second_cleanup = open_zip_pages_for_viewer(archive_path)
    try:
        assert isinstance(first, LazyZipPageList)
        assert isinstance(second, LazyZipPageList)
        assert first[0] != second[0]
        assert first.cache_source_identity(0) == second.cache_source_identity(0)
    finally:
        shutil.rmtree(first_cleanup, ignore_errors=True)
        shutil.rmtree(second_cleanup, ignore_errors=True)


def test_zip_materialize_reextracts_when_cached_file_disappears(tmp_path: Path) -> None:
    archive_path = tmp_path / "recreate.zip"
    image = io.BytesIO()
    Image.new("RGB", (16, 16), (20, 210, 40)).save(image, format="PNG")
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("chapter/001.png", image.getvalue())

    pages, cleanup = open_zip_pages_for_viewer(archive_path)
    try:
        extracted = pages[0]
        extracted.unlink()

        recreated = pages[0]

        assert recreated == extracted
        assert recreated.is_file()
        with Image.open(recreated) as reopened:
            assert reopened.convert("RGB").getpixel((0, 0)) == (20, 210, 40)
    finally:
        shutil.rmtree(cleanup, ignore_errors=True)


def test_zip_materialize_serializes_parallel_extraction(tmp_path: Path) -> None:
    archive_path = tmp_path / "parallel.zip"
    image = io.BytesIO()
    Image.new("RGB", (16, 16), (20, 210, 40)).save(image, format="PNG")
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("chapter/001.png", image.getvalue())

    pages, cleanup = open_zip_pages_for_viewer(archive_path)
    copy_calls: list[None] = []
    copy_calls_lock = threading.Lock()
    original_copy = page_provider.copy_stream_limited

    def slow_copy(*args, **kwargs):
        with copy_calls_lock:
            copy_calls.append(None)
        time.sleep(0.02)
        return original_copy(*args, **kwargs)

    try:
        with (
            patch.object(page_provider, "copy_stream_limited", side_effect=slow_copy),
            ThreadPoolExecutor(max_workers=8) as executor,
        ):
            extracted = list(executor.map(pages.materialize, [0] * 8))

        assert len(copy_calls) == 1
        assert len(set(extracted)) == 1
        assert extracted[0].is_file()
    finally:
        shutil.rmtree(cleanup, ignore_errors=True)
