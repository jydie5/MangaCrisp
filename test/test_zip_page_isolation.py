import io
import shutil
import warnings
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from mangacrisp_app.archive_utils import archive_member_output_path
from mangacrisp_app.page_provider import LazyZipPageList, open_zip_pages_for_viewer

Color = tuple[int, int, int]


def _png_bytes(color: Color) -> bytes:
    image = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(image, format="PNG")
    return image.getvalue()


def _write_zip(path: Path, members: list[tuple[str, Color]]) -> None:
    # zipfile warns when a fixture intentionally contains duplicate names.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            for name, color in members:
                archive.writestr(name, _png_bytes(color))


def _pixel(path: Path) -> Color:
    with Image.open(path) as image:
        return image.convert("RGB").getpixel((0, 0))


def _assert_isolated_round_trip(pages: LazyZipPageList, expected: set[Color]) -> None:
    first_path = pages[0]
    first_color = _pixel(first_path)
    second_path = pages[1]
    second_color = _pixel(second_path)

    assert first_path != second_path
    assert first_path.parent != second_path.parent
    assert {first_color, second_color} == expected

    # A later extraction must not overwrite the earlier page's file.
    assert pages[0] == first_path
    assert pages[1] == second_path
    assert _pixel(pages[0]) == first_color
    assert _pixel(pages[1]) == second_color


def test_zip_duplicate_names_are_isolated_and_keep_cache_identity(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.zip"
    red = (230, 30, 40)
    blue = (30, 50, 230)
    _write_zip(source, [("pages/same.png", red), ("pages/same.png", blue)])

    pages, cleanup = open_zip_pages_for_viewer(source)
    try:
        identity = pages.cache_source_identity(0)
        _assert_isolated_round_trip(pages, {red, blue})

        assert pages[0].name == "same.png"
        assert pages[1].name == "same.png"
        assert pages.page_stem(0) == pages.page_stem(1) == "same"
        assert pages.cache_source_identity(0) == identity
        assert "member=pages/same.png" in identity
        assert pages.cache_source_identity(0) != pages.cache_source_identity(1)
    finally:
        shutil.rmtree(cleanup, ignore_errors=True)


def test_zip_sanitized_names_are_isolated_and_keep_safe_stems(tmp_path: Path) -> None:
    source = tmp_path / "sanitized.zip"
    red = (230, 30, 40)
    blue = (30, 50, 230)
    _write_zip(source, [("pages/a?.png", red), ("pages/a*.png", blue)])

    pages, cleanup = open_zip_pages_for_viewer(source)
    try:
        _assert_isolated_round_trip(pages, {red, blue})
        assert pages[0].name == "a_.png"
        assert pages[1].name == "a_.png"
        assert pages.page_stem(0) == pages.page_stem(1) == "a_"
        assert pages.cache_source_identity(0) != pages.cache_source_identity(1)
    finally:
        shutil.rmtree(cleanup, ignore_errors=True)


def test_zip_casefold_names_are_isolated_by_private_parent(tmp_path: Path) -> None:
    source = tmp_path / "casefold.zip"
    upper = (230, 30, 40)
    lower = (30, 50, 230)
    _write_zip(source, [("pages/A.png", upper), ("pages/a.png", lower)])

    pages, cleanup = open_zip_pages_for_viewer(source)
    try:
        _assert_isolated_round_trip(pages, {upper, lower})
        assert pages[0].name == "A.png"
        assert pages[1].name == "a.png"
        assert pages[0].parents[1].name == ".page-000000"
        assert pages[1].parents[1].name == ".page-000001"
    finally:
        shutil.rmtree(cleanup, ignore_errors=True)


def test_extraction_path_is_metadata_only_and_supports_negative_index(tmp_path: Path) -> None:
    source = tmp_path / "metadata.zip"
    _write_zip(source, [("chapter/001.png", (30, 50, 230))])

    pages, cleanup = open_zip_pages_for_viewer(source)
    try:
        expected = archive_member_output_path(cleanup / ".page-000000", "chapter/001.png")
        assert expected is not None
        assert pages.extraction_path(-1) == expected
        assert pages.page_stem(-1) == "001"
        assert list(cleanup.iterdir()) == []
        assert not expected.exists()
        with pytest.raises(IndexError):
            pages.extraction_path(-2)
        with pytest.raises(IndexError):
            pages.extraction_path(1)
    finally:
        shutil.rmtree(cleanup, ignore_errors=True)


def test_extraction_path_rejects_unsafe_member_without_creating_directory(tmp_path: Path) -> None:
    source = tmp_path / "empty.zip"
    source.write_bytes(b"")
    extraction_root = tmp_path / "extract"
    pages = LazyZipPageList(source, extraction_root, [zipfile.ZipInfo("../escape.png")])

    with pytest.raises(RuntimeError, match="unsafe archive member"):
        pages.extraction_path(0)
    assert not extraction_root.exists()
