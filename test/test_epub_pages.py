from __future__ import annotations

import io
import os
import shutil
import unicodedata
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from mangacrisp_app.archive_utils import archive_member_output_path
from mangacrisp_app.epub_pages import EpubPageList, open_epub_image_pages
from mangacrisp_app.epub_probe import EpubProbeError
from mangacrisp_app.page_provider import LazyZipPageList

CONTAINER = b"""<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""


def _image_bytes(color: tuple[int, int, int], image_format: str = "PNG") -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (24, 36), color).save(stream, format=image_format)
    return stream.getvalue()


def _opf(
    items: list[tuple[str, str, str]],
    spine: list[tuple[str, bool, str]],
    *,
    direction: str = "rtl",
    cover: str | None = None,
    fixed_layout: bool = True,
) -> bytes:
    manifest = "\n".join(
        _manifest_item(item_id, href, media_type, cover)
        for item_id, href, media_type in items
    )
    refs = "\n".join(
        _spine_item(item_id, linear, properties)
        for item_id, linear, properties in spine
    )
    layout_metadata = (
        '<meta property="rendition:layout">pre-paginated</meta>' if fixed_layout else ""
    )
    return f'''<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Direct images</dc:title>{layout_metadata}
  </metadata>
  <manifest>{manifest}</manifest>
  <spine page-progression-direction="{direction}">{refs}</spine>
</package>'''.encode()


def _manifest_item(item_id: str, href: str, media_type: str, cover: str | None) -> str:
    cover_attribute = ' properties="cover-image"' if item_id == cover else ""
    return f'<item id="{item_id}" href="{href}" media-type="{media_type}"{cover_attribute}/>'


def _spine_item(item_id: str, linear: bool, properties: str) -> str:
    linear_attribute = "" if linear else ' linear="no"'
    properties_attribute = f' properties="{properties}"' if properties else ""
    return f'<itemref idref="{item_id}"{linear_attribute}{properties_attribute}/>'


def _epub(
    path: Path,
    *,
    items: list[tuple[str, str, str]],
    spine: list[tuple[str, bool, str]],
    resources: dict[str, bytes],
    direction: str = "rtl",
    cover: str | None = None,
    fixed_layout: bool = True,
) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED
        )
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr(
            "OPS/book.opf",
            _opf(
                items,
                spine,
                direction=direction,
                cover=cover,
                fixed_layout=fixed_layout,
            ),
        )
        for name, data in resources.items():
            archive.writestr(name, data)
    return path


def _basic_epub(path: Path) -> Path:
    return _epub(
        path,
        items=[
            ("one", "Images/one.png", "image/png"),
            ("two", "Images/two.jpg", "image/jpeg"),
            ("aux", "Images/aux.png", "image/png"),
        ],
        spine=[
            ("two", True, "page-spread-left"),
            ("aux", False, ""),
            ("one", True, "page-spread-right"),
        ],
        resources={
            "OPS/Images/one.png": _image_bytes((210, 30, 20)),
            "OPS/Images/two.jpg": _image_bytes((20, 210, 30), "JPEG"),
            "OPS/Images/aux.png": _image_bytes((20, 30, 210)),
        },
        cover="one",
    )


def test_epub_image_pages_are_lazy_spine_ordered_and_keep_metadata(
    tmp_path: Path,
) -> None:
    pages, cleanup = open_epub_image_pages(_basic_epub(tmp_path / "comic.epub"))
    try:
        assert isinstance(pages, EpubPageList)
        assert isinstance(pages, LazyZipPageList)
        assert len(pages) == 2
        assert pages.extracted == {}
        assert pages.metadata.direction == "rtl"
        assert pages.metadata.cover_path == "OPS/Images/one.png"
        assert [entry.spread_position for entry in pages.spine] == ["left", "right"]
        assert pages.page_stem(0) == "two"

        first = pages[0]
        second = pages[-1]
        with Image.open(first) as image:
            assert image.convert("RGB").getpixel((0, 0))[1] > 150
        with Image.open(second) as image:
            assert image.convert("RGB").getpixel((0, 0))[0] > 150
        assert set(pages.extracted) == {0, 1}
        with pytest.raises(IndexError):
            _ = pages[2]
        with pytest.raises(IndexError):
            pages.page_stem(-3)
    finally:
        pages.close()
    assert not cleanup.exists()


def test_300_epub_pages_open_without_extracting_or_decoding_then_extract_one(
    tmp_path: Path,
) -> None:
    items = [
        (f"page-{index}", f"Images/{index:03d}.png", "image/png")
        for index in range(300)
    ]
    source = _epub(
        tmp_path / "large.epub",
        items=items,
        spine=[(item_id, True, "") for item_id, _, _ in items],
        resources={
            f"OPS/Images/{index:03d}.png": _image_bytes((index % 255, 80, 160))
            for index in range(300)
        },
    )
    pages, cleanup = open_epub_image_pages(source)
    try:
        assert len(pages) == 300
        assert pages.extracted == {}
        with patch("mangacrisp_app.epub_pages.Image.open", wraps=Image.open) as opener:
            selected = pages[150]
        assert selected.is_file()
        assert set(pages.extracted) == {150}
        assert opener.call_count == 1
    finally:
        pages.close()
    assert not cleanup.exists()


def test_repeated_spine_entry_is_a_distinct_physical_index(tmp_path: Path) -> None:
    source = _epub(
        tmp_path / "repeat.epub",
        items=[("one", "Images/one.png", "image/png")],
        spine=[("one", True, ""), ("one", True, "")],
        resources={"OPS/Images/one.png": _image_bytes((20, 210, 40))},
    )
    pages, cleanup = open_epub_image_pages(source)
    try:
        assert len(pages) == 2
        assert pages.cache_source_identity(0) != pages.cache_source_identity(1)
        assert pages[0].is_file()
        assert pages[1].is_file()
        assert set(pages.extracted) == {0, 1}
    finally:
        pages.close()
    assert not cleanup.exists()


def test_all_direct_images_are_accepted_when_package_layout_is_reflowable(
    tmp_path: Path,
) -> None:
    source = _epub(
        tmp_path / "reflowable-images.epub",
        items=[("one", "Images/one.png", "image/png")],
        spine=[("one", True, "")],
        resources={"OPS/Images/one.png": _image_bytes((20, 210, 40))},
        fixed_layout=False,
    )
    pages, cleanup = open_epub_image_pages(source)
    try:
        assert pages.metadata.global_layout == "reflowable"
        assert pages.metadata.content_profile == "direct-image-candidate"
        assert pages[0].is_file()
    finally:
        pages.close()
    assert not cleanup.exists()


def test_direct_images_keep_mixed_layout_metadata_without_rejection(
    tmp_path: Path,
) -> None:
    source = _epub(
        tmp_path / "mixed-layout.epub",
        items=[
            ("one", "Images/one.png", "image/png"),
            ("two", "Images/two.png", "image/png"),
        ],
        spine=[
            ("one", True, "rendition:layout-reflowable"),
            ("two", True, ""),
        ],
        resources={
            "OPS/Images/one.png": _image_bytes((20, 210, 40)),
            "OPS/Images/two.png": _image_bytes((20, 30, 210)),
        },
    )
    pages, cleanup = open_epub_image_pages(source)
    try:
        assert pages.metadata.effective_layout == "mixed"
        assert "mixed-layout" in pages.metadata.warnings
        assert pages[0].is_file()
    finally:
        pages.close()
    assert not cleanup.exists()


def test_reextracted_page_is_validated_again_after_its_temp_file_disappears(
    tmp_path: Path,
) -> None:
    pages, cleanup = open_epub_image_pages(_basic_epub(tmp_path / "reextract.epub"))
    try:
        extracted = pages[0]
        extracted.unlink()
        with patch("mangacrisp_app.epub_pages.Image.open", wraps=Image.open) as opener:
            recreated = pages[0]
        assert recreated.is_file()
        assert opener.call_count == 1
    finally:
        pages.close()
    assert not cleanup.exists()


def test_archive_read_error_is_corrupt_and_removes_requested_output(
    tmp_path: Path,
) -> None:
    pages, cleanup = open_epub_image_pages(_basic_epub(tmp_path / "read-error.epub"))
    try:
        output = archive_member_output_path(cleanup, pages.members[0].filename)
        assert output is not None
        output.parent.mkdir(parents=True)
        output.write_bytes(b"partial")
        with (
            patch.object(
                LazyZipPageList,
                "materialize",
                side_effect=zipfile.BadZipFile("bad zip"),
            ),
            pytest.raises(EpubProbeError) as error,
        ):
            _ = pages[0]
        assert error.value.reason == "corrupt"
        assert not output.exists()
        assert pages.extracted == {}
    finally:
        pages.close()


def test_decompression_bomb_is_archive_abuse_only_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pages, _cleanup = open_epub_image_pages(_basic_epub(tmp_path / "bomb.epub"))
    try:
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)
        with pytest.raises(EpubProbeError) as error:
            _ = pages[0]
        assert error.value.reason == "archive-abuse"
        assert pages.extracted == {}
    finally:
        pages.close()


def test_page_stem_uses_safe_output_name_without_extracting(tmp_path: Path) -> None:
    source = _epub(
        tmp_path / "stem.epub",
        items=[("one", "Images/a%3Fb.png", "image/png")],
        spine=[("one", True, "")],
        resources={"OPS/Images/a?b.png": _image_bytes((20, 210, 40))},
    )
    pages, cleanup = open_epub_image_pages(source)
    try:
        assert pages.page_stem(0) == "a_b"
        assert pages.extracted == {}
        assert not list(cleanup.rglob("*"))
    finally:
        pages.close()


def test_close_is_terminal_and_does_not_recreate_the_temp_directory(
    tmp_path: Path,
) -> None:
    pages, cleanup = open_epub_image_pages(_basic_epub(tmp_path / "closed.epub"))
    pages.close()
    assert not cleanup.exists()
    with pytest.raises(RuntimeError, match="closed"):
        _ = pages[0]
    with pytest.raises(RuntimeError, match="closed"):
        pages.page_stem(0)
    with pytest.raises(RuntimeError, match="closed"):
        pages.cache_source_identity(0)


@pytest.mark.parametrize(
    ("media_type", "payload"),
    [("image/jpeg", _image_bytes((20, 30, 210))), ("image/png", b"not an image")],
)
def test_bad_or_mismatched_image_is_rejected_only_when_requested(
    tmp_path: Path, media_type: str, payload: bytes
) -> None:
    source = _epub(
        tmp_path / "bad-image.epub",
        items=[("one", "Images/one.bin", media_type)],
        spine=[("one", True, "")],
        resources={"OPS/Images/one.bin": payload},
    )
    pages, cleanup = open_epub_image_pages(source)
    try:
        assert pages.extracted == {}
        with pytest.raises(EpubProbeError) as error:
            _ = pages[0]
        assert error.value.reason == "corrupt"
        assert pages.extracted == {}
        assert not list(cleanup.rglob("*"))
    finally:
        pages.close()


@pytest.mark.parametrize(
    "media_type", ["application/xhtml+xml", "image/svg+xml", "application/x-private"]
)
def test_non_direct_image_profiles_remain_unsupported_without_temp_extraction(
    tmp_path: Path, media_type: str
) -> None:
    source = _epub(
        tmp_path / "unsupported.epub",
        items=[("one", "Images/one.bin", media_type)],
        spine=[("one", True, "")],
        resources={"OPS/Images/one.bin": b"payload"},
    )
    original = source.read_bytes()
    with pytest.raises(EpubProbeError) as error:
        open_epub_image_pages(source)
    assert error.value.reason == "unsupported"
    assert source.read_bytes() == original


def test_nfd_member_names_map_to_nfc_probe_paths_and_cleanup_is_explicit(
    tmp_path: Path,
) -> None:
    nfd_name = unicodedata.normalize("NFD", "Images/é.png")
    source = _epub(
        tmp_path / "nfd.epub",
        items=[("one", nfd_name, "image/png")],
        spine=[("one", True, "")],
        resources={f"OPS/{nfd_name}": _image_bytes((20, 210, 40))},
    )
    pages, cleanup = open_epub_image_pages(source)
    assert pages[0].is_file()
    pages.close()
    assert not cleanup.exists()


def test_epub_source_identity_changes_when_archive_changes(tmp_path: Path) -> None:
    source = _basic_epub(tmp_path / "changing.epub")
    first, first_cleanup = open_epub_image_pages(source)
    try:
        first_identity = first.cache_source_identity(0)
    finally:
        first.close()
    _basic_epub(source)
    stat = source.stat()
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    second, second_cleanup = open_epub_image_pages(source)
    try:
        assert second.cache_source_identity(0) != first_identity
    finally:
        second.close()
    assert not first_cleanup.exists()
    assert not second_cleanup.exists()


def test_caller_may_use_returned_cleanup_directory_directly(tmp_path: Path) -> None:
    pages, cleanup = open_epub_image_pages(_basic_epub(tmp_path / "cleanup.epub"))
    _ = pages[0]
    shutil.rmtree(cleanup)
    assert not cleanup.exists()
