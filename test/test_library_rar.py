from __future__ import annotations

from pathlib import Path

import pytest
import rarfile

from mangacrisp_app import library
from mangacrisp_app.library import LibraryPaths, LibraryService


def importer(tmp_path: Path):
    return LibraryService.open(LibraryPaths.for_base_dir(tmp_path / "state")).importer


class _Info:
    def __init__(self, filename: str) -> None:
        self.filename = filename

    def isdir(self) -> bool:
        return False


class _RarWithoutTool:
    """Lists members like rarfile does, but cannot decompress (no unrar tool)."""

    def __init__(self, _path) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def infolist(self):
        return [_Info("book/001.jpg"), _Info("book/002.jpg")]

    def open(self, _info):
        raise rarfile.RarCannotExec("Cannot find working tool")


def test_rar_extraction_falls_back_to_7zip_without_unrar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = importer(tmp_path)
    monkeypatch.setattr(rarfile, "RarFile", _RarWithoutTool)
    calls: list[dict] = []

    def external(archive_path, pages_dir, member_names=None, primary_error=None):
        calls.append({"member_names": member_names, "error": primary_error})
        return [pages_dir / "000001.jpg"]

    monkeypatch.setattr(service, "_extract_external_pages", external)

    (tmp_path / "pages").mkdir()
    pages = service._extract_rar_pages(tmp_path / "book.rar", tmp_path / "pages", member_names={"book/001.jpg"})

    assert pages == [tmp_path / "pages" / "000001.jpg"]
    assert calls[0]["member_names"] == {"book/001.jpg"}
    assert isinstance(calls[0]["error"], rarfile.RarCannotExec)


def test_external_extraction_keeps_only_the_selected_volume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = importer(tmp_path)
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()

    def extract_all(archive_path, temp_dir, member_names=None, primary_error=None):
        # 7-Zip always extracts the whole multi-volume archive.
        for volume in ("vol1", "vol2"):
            for page in ("001.jpg", "002.jpg"):
                target = temp_dir / "series" / volume / page
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"image")

    monkeypatch.setattr(library, "extract_external_archive_images", extract_all)

    pages = service._extract_external_pages(
        tmp_path / "series.rar",
        pages_dir,
        member_names={"series/vol2/001.jpg", "series/vol2/002.jpg"},
    )

    assert len(pages) == 2
    assert sorted(path.name for path in pages_dir.rglob("*") if path.is_file()) == ["000001.jpg", "000002.jpg"]
