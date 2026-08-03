import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from mangacrisp_app.archive_utils import (
    ArchiveImageMember,
    archive_member_output_path,
    copy_stream_limited,
    list_zip_image_members,
    validate_archive_members,
    validate_extracted_tree,
)
from mangacrisp_app.page_provider import open_pages_for_viewer


def test_archive_member_path_rejects_traversal_and_absolute_paths(tmp_path: Path) -> None:
    assert archive_member_output_path(tmp_path, "../page.png") is None
    assert archive_member_output_path(tmp_path, "/tmp/page.png") is None
    assert archive_member_output_path(tmp_path, "C:\\temp\\page.png") is None
    assert archive_member_output_path(tmp_path, "pages/001.png") == tmp_path / "pages" / "001.png"


def test_zip_listing_rejects_unsafe_image_name(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../outside.png", b"not-an-image")

    with pytest.raises(RuntimeError, match="unsafe archive member path"):
        list_zip_image_members(archive_path)

    with pytest.raises(RuntimeError, match="unsafe archive member path"):
        open_pages_for_viewer(archive_path)


def test_archive_member_limits_reject_large_or_extreme_entries() -> None:
    with pytest.raises(RuntimeError, match="too large"):
        validate_archive_members([ArchiveImageMember("page.png", 600 * 1024 * 1024, 1000)])
    with pytest.raises(RuntimeError, match="compression ratio"):
        validate_archive_members([ArchiveImageMember("page.png", 10_000_000, 1)])


def test_copy_stream_stops_after_limit() -> None:
    with pytest.raises(RuntimeError, match="safety limit"):
        copy_stream_limited(io.BytesIO(b"123456"), io.BytesIO(), max_bytes=5)


def test_extracted_tree_rejects_symbolic_links(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (8, 8), "red").save(source)
    link = tmp_path / "linked.png"
    link.symlink_to(source)

    with pytest.raises(RuntimeError, match="symbolic link"):
        validate_extracted_tree(tmp_path)
