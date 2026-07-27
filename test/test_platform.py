from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from mangacrisp_app import engine_utils
from mangacrisp_app.archive_utils import (
    external_archive_extract_command,
    external_archive_tool,
)
from mangacrisp_app.platform import windows as windows_platform
from mangacrisp_app.platform.macos import application_directories as macos_directories
from mangacrisp_app.platform.windows import (
    application_directories as windows_directories,
    engine_executable_names,
    bundled_archive_tool_candidates,
    open_directory as open_windows_directory,
    subprocess_window_kwargs,
)
from mangacrisp_app.viewer import parse_args, should_open_bookshelf


def test_smoke_test_opens_isolated_bookshelf() -> None:
    args = parse_args(["mangacrisp", "--smoke-test"])

    assert args.smoke_test is True
    assert should_open_bookshelf(args) is True


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


def test_windows_bundled_archive_tool_is_next_to_frozen_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "MangaCrisp.exe"
    monkeypatch.setattr(windows_platform.sys, "executable", str(executable))
    monkeypatch.delattr(windows_platform.sys, "_MEIPASS", raising=False)

    assert bundled_archive_tool_candidates() == (
        tmp_path / "tools" / "7zip" / "7z.exe",
        tmp_path / "tools" / "7zip" / "7zz.exe",
    )


def test_configured_archive_tool_takes_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "custom-7z.exe"
    executable.write_bytes(b"test")
    monkeypatch.setenv("MANGACRISP_ARCHIVE_TOOL_PATH", str(executable))

    assert external_archive_tool("7zz", "7z") == str(executable)
    assert external_archive_extract_command(
        tmp_path / "book.cbr",
        tmp_path / "pages",
    ) == [
        str(executable),
        "x",
        "-y",
        f"-o{tmp_path / 'pages'}",
        str(tmp_path / "book.cbr"),
    ]
