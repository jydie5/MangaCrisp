from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from mangacrisp_app.capture.session import CaptureSession, safe_session_name


def color_image(color: tuple[int, int, int], size: tuple[int, int] = (320, 480)) -> Image.Image:
    return Image.new("RGB", size, color)


def test_session_captures_undoes_and_reuses_number(tmp_path: Path) -> None:
    session = CaptureSession.create(
        tmp_path,
        "Demo Book",
        created_at=datetime(2026, 8, 12, 9, 0, 0, tzinfo=UTC),
    )
    first = session.capture(color_image((20, 30, 40)))
    second = session.capture(color_image((40, 50, 60)))

    assert first.position == 1
    assert second.file == "pages/000002.png"
    assert session.undo_last().position == 2
    replacement = session.capture(color_image((70, 80, 90)))
    assert replacement.position == 2
    assert (session.directory / replacement.file).is_file()
    assert len(CaptureSession.open(session.directory).pages) == 2


def test_session_detects_exact_duplicate_and_black_frame(tmp_path: Path) -> None:
    session = CaptureSession.create(tmp_path, "Warnings")
    source = color_image((100, 120, 140))
    session.capture(source)
    duplicate = session.capture(source)
    black = session.capture(color_image((0, 0, 0)))

    assert "duplicate" in {warning.code for warning in duplicate.warnings}
    assert "black" in {warning.code for warning in black.warnings}


def test_reorder_delete_rotate_and_package_are_naturally_numbered(tmp_path: Path) -> None:
    session = CaptureSession.create(tmp_path, "Package")
    for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
        session.capture(color_image(color))
    session.reorder([3, 1, 2])
    session.delete(2)
    rotated = session.rotate(1)
    output = session.package()

    assert (rotated.width, rotated.height) == (480, 320)
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["000001.png", "000002.png"]
        assert archive.testzip() is None
    assert [page.position for page in session.pages] == [1, 2]


def test_session_rejects_unknown_manifest_and_unsafe_page(tmp_path: Path) -> None:
    session = CaptureSession.create(tmp_path, "Unsafe")
    manifest = json.loads(session.manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 2
    session.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported"):
        CaptureSession.open(session.directory)

    manifest["schema_version"] = 1
    manifest["pages"] = [
        {
            "position": 1,
            "file": "../outside.png",
            "sha256": "x",
            "perceptual_hash": "0" * 16,
            "width": 100,
            "height": 100,
            "warnings": [],
        }
    ]
    session.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="missing or unsafe"):
        CaptureSession.open(session.directory)


def test_safe_session_name_removes_path_characters() -> None:
    assert safe_session_name(" ../My:Book/01 ") == "My-Book-01"
    assert safe_session_name("許諾済み 漫画") == "許諾済み 漫画"


def test_retake_after_reorder_does_not_overwrite_another_page(tmp_path: Path) -> None:
    session = CaptureSession.create(tmp_path, "Retake")
    for color in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
        session.capture(color_image(color))
    session.reorder([3, 1, 2])
    other_page_file = session.directory / session.pages[1].file
    other_page_before = other_page_file.read_bytes()

    retaken = session.capture(color_image((200, 200, 0)), replace_position=1)

    assert retaken.file == "pages/000003.png"
    assert other_page_file.read_bytes() == other_page_before
