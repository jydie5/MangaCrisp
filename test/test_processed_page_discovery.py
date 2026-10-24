from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from mangacrisp_app.page_provider import (
    LazyZipPageList,
    PdfPageList,
    open_pages_for_viewer,
)
from mangacrisp_app.viewer import collect_processed_pages

PAGE_COUNT = 300


def _make_pdf(path: Path, count: int = PAGE_COUNT) -> None:
    images = [Image.new("RGB", (16, 16), (index % 255, 80, 160)) for index in range(count)]
    try:
        images[0].save(path, format="PDF", save_all=True, append_images=images[1:])
    finally:
        for image in images:
            image.close()


def _make_zip(path: Path, count: int = PAGE_COUNT) -> None:
    image = io.BytesIO()
    source = Image.new("RGB", (16, 16), (20, 210, 40))
    try:
        source.save(image, format="PNG")
    finally:
        source.close()
    payload = image.getvalue()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index in range(count):
            archive.writestr(f"pages/{index:04d}.png", payload)


def test_empty_processed_lookup_keeps_300_page_pdf_lazy(tmp_path: Path) -> None:
    source = tmp_path / "many.pdf"
    _make_pdf(source)
    pages, cleanup = open_pages_for_viewer(source, pdf_cache_dir=tmp_path / "pdf-cache")
    assert cleanup is None
    assert isinstance(pages, PdfPageList)
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()

    result = collect_processed_pages(pages, processed_dir)

    assert result == [None] * PAGE_COUNT
    assert pages.extracted == {}
    assert list(pages.cache_dir.rglob("*.png")) == []


def test_empty_processed_lookup_keeps_300_page_zip_lazy(tmp_path: Path) -> None:
    source = tmp_path / "many.zip"
    _make_zip(source)
    pages, cleanup = open_pages_for_viewer(source)
    assert isinstance(pages, LazyZipPageList)
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    try:
        result = collect_processed_pages(pages, processed_dir)

        assert result == [None] * PAGE_COUNT
        assert pages.extracted == {}
        assert [path for path in pages.temp_dir.rglob("*") if path.is_file()] == []
    finally:
        shutil.rmtree(cleanup, ignore_errors=True)


def test_provider_page_stem_matches_existing_names_without_materializing(tmp_path: Path) -> None:
    pdf = tmp_path / "book.pdf"
    _make_pdf(pdf, count=2)
    pdf_pages, cleanup = open_pages_for_viewer(pdf, pdf_cache_dir=tmp_path / "pdf-cache")
    assert cleanup is None
    assert isinstance(pdf_pages, PdfPageList)
    assert pdf_pages.page_stem(0) == "000001"
    assert pdf_pages.page_stem(-1) == "000002"
    assert pdf_pages.extracted == {}

    archive = tmp_path / "book.zip"
    _make_zip(archive, count=2)
    zip_pages, zip_cleanup = open_pages_for_viewer(archive)
    assert isinstance(zip_pages, LazyZipPageList)
    try:
        assert zip_pages.page_stem(0) == "0000"
        assert zip_pages.page_stem(-1) == "0001"
        assert zip_pages.extracted == {}
    finally:
        shutil.rmtree(zip_cleanup, ignore_errors=True)

    for pages in (pdf_pages, zip_pages):
        with pytest.raises(IndexError):
            pages.page_stem(-len(pages) - 1)
        with pytest.raises(IndexError):
            pages.page_stem(len(pages))


def test_processed_lookup_matches_provider_prefixes_without_indexing(tmp_path: Path) -> None:
    source = tmp_path / "book.pdf"
    _make_pdf(source, count=2)
    pages, _cleanup = open_pages_for_viewer(source, pdf_cache_dir=tmp_path / "pdf-cache")
    assert isinstance(pages, PdfPageList)
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    first = processed_dir / "0001_000001_x3.png"
    second = processed_dir / "0002_000002_x3.png"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    assert collect_processed_pages(pages, processed_dir) == [first.resolve(), second.resolve()]
    assert pages.extracted == {}


def test_processed_lookup_keeps_normal_path_lists_and_none_early_return(tmp_path: Path) -> None:
    pages = [tmp_path / "page one.png", tmp_path / "page two.png"]
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    first = processed_dir / "0001_page one_x3.png"
    first.write_bytes(b"first")

    assert collect_processed_pages(pages, processed_dir) == [first.resolve(), None]
    assert collect_processed_pages(pages, None) == [None, None]


def test_processed_lookup_escapes_literal_stem_metacharacters(tmp_path: Path) -> None:
    pages = [Path("page[1].png")]
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    wrong = processed_dir / "0001_page1_wrong.png"
    expected = processed_dir / "0001_page[1]_x3.png"
    wrong.write_bytes(b"wrong")
    expected.write_bytes(b"expected")

    assert collect_processed_pages(pages, processed_dir) == [expected.resolve()]

