from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from mangacrisp_app import engine_utils
from mangacrisp_app.platform.macos import application_directories as macos_directories
from mangacrisp_app.platform.windows import (
    application_directories as windows_directories,
    engine_executable_names,
    open_directory as open_windows_directory,
    subprocess_window_kwargs,
)


def test_macos_application_directories_preserve_existing_layout(tmp_path: Path) -> None:
    paths = macos_directories("MangaCrisp", "RAIV", home=tmp_path)

    assert paths.app_support_dir == tmp_path / "Library" / "Application Support" / "MangaCrisp"
    assert paths.cache_dir == tmp_path / "Library" / "Caches" / "MangaCrisp"
    assert paths.default_library_dir == tmp_path / "MangaCrisp Library"


def test_windows_application_directories_use_roaming_and_local_data(tmp_path: Path) -> None:
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    paths = windows_directories(
        "MangaCrisp",
        "RAIV",
        home=tmp_path / "Home",
        environ={"APPDATA": str(roaming), "LOCALAPPDATA": str(local)},
    )

    assert paths.app_support_dir == roaming / "MangaCrisp"
    assert paths.cache_dir == local / "MangaCrisp"
    assert paths.default_library_dir == tmp_path / "Home" / "MangaCrisp Library"
    assert paths.legacy_app_support_dir == roaming / "RAIV"


def test_windows_engine_executable_name_prefers_exe() -> None:
    assert engine_executable_names("realcugan-ncnn-vulkan") == (
        "realcugan-ncnn-vulkan.exe",
        "realcugan-ncnn-vulkan",
    )


def test_windows_open_directory_uses_shell(tmp_path: Path) -> None:
    with patch("mangacrisp_app.platform.windows.os.startfile", create=True) as startfile:
        open_windows_directory(tmp_path)

    startfile.assert_called_once_with(str(tmp_path))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only process flag")
def test_windows_subprocesses_hide_console_windows() -> None:
    assert subprocess_window_kwargs()["creationflags"] != 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only executable name")
def test_realcugan_detection_finds_windows_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = (
        tmp_path
        / "tools"
        / "realcugan-ncnn-vulkan"
        / "realcugan-ncnn-vulkan.exe"
    )
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"exe")
    monkeypatch.setattr(engine_utils, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(engine_utils, "ENGINES_DIR", tmp_path / "test" / "engines")
    monkeypatch.setattr(engine_utils, "bundled_root", lambda: None)
    monkeypatch.delenv("MANGACRISP_REALCUGAN_PATH", raising=False)

    assert engine_utils.realcugan_executable() == executable
