from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fetch_realcugan_linux.py"
SPEC = importlib.util.spec_from_file_location("fetch_realcugan_linux", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
fetch_realcugan_linux = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_realcugan_linux)


def make_tool_dir(root: Path, executable_bytes: bytes = b"engine") -> Path:
    tool_dir = root / fetch_realcugan_linux.PACKAGE_ROOT
    tool_dir.mkdir(parents=True)
    (tool_dir / "realcugan-ncnn-vulkan").write_bytes(executable_bytes)
    (tool_dir / "LICENSE").write_text("MIT", encoding="utf-8")
    (tool_dir / "README.md").write_text("readme", encoding="utf-8")
    for directory in fetch_realcugan_linux.REQUIRED_MODEL_DIRS:
        (tool_dir / directory).mkdir()
        (tool_dir / directory / "up2x.bin").write_bytes(b"bin")
        (tool_dir / directory / "up2x.param").write_bytes(b"param")
    return tool_dir


def test_linux_realcugan_pin_is_official_ubuntu_release() -> None:
    assert fetch_realcugan_linux.ARCHIVE_URL.startswith(
        "https://github.com/nihui/realcugan-ncnn-vulkan/releases/download/20220728/"
    )
    assert fetch_realcugan_linux.ARCHIVE_URL.endswith("-ubuntu.zip")
    assert len(fetch_realcugan_linux.ARCHIVE_SHA256) == 64
    assert len(fetch_realcugan_linux.EXECUTABLE_SHA256) == 64


def test_linux_realcugan_verification_requires_pinned_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool_dir = make_tool_dir(tmp_path)
    assert fetch_realcugan_linux.verify_tool_directory(tool_dir) is False

    monkeypatch.setattr(
        fetch_realcugan_linux,
        "EXECUTABLE_SHA256",
        fetch_realcugan_linux.sha256_file(tool_dir / "realcugan-ncnn-vulkan"),
    )
    assert fetch_realcugan_linux.verify_tool_directory(tool_dir) is True

    (tool_dir / "models-se" / "up2x.param").unlink()
    assert fetch_realcugan_linux.verify_tool_directory(tool_dir) is False


def test_linux_realcugan_rejects_unsafe_zip_members(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.txt", "bad")
    with zipfile.ZipFile(buffer) as archive, pytest.raises(RuntimeError, match="unsafe"):
        fetch_realcugan_linux.safe_extract(archive, tmp_path / "out")


def test_linux_realcugan_extraction_restores_executable_bit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_tool_dir(tmp_path / "source")
    archive_path = tmp_path / "cache" / fetch_realcugan_linux.ARCHIVE_NAME
    archive_path.parent.mkdir()
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in source.rglob("*"):
            archive.write(path, path.relative_to(source.parent).as_posix())
    monkeypatch.setattr(
        fetch_realcugan_linux,
        "ARCHIVE_SHA256",
        fetch_realcugan_linux.sha256_file(archive_path),
    )
    monkeypatch.setattr(
        fetch_realcugan_linux,
        "EXECUTABLE_SHA256",
        fetch_realcugan_linux.sha256_file(source / "realcugan-ncnn-vulkan"),
    )

    tool_dir = fetch_realcugan_linux.ensure_realcugan(tmp_path / "engines", tmp_path / "cache")

    assert (tool_dir / "realcugan-ncnn-vulkan").stat().st_mode & 0o111
    provenance = fetch_realcugan_linux.write_provenance(tmp_path / "licenses", tool_dir)
    assert '"architecture": "x86_64"' in provenance.read_text(encoding="utf-8")

