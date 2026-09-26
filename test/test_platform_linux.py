from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from mangacrisp_app.platform import linux as linux_platform


def test_linux_application_directories_follow_xdg(tmp_path: Path) -> None:
    paths = linux_platform.application_directories(
        "MangaCrisp",
        "RAIV",
        home=tmp_path / "home",
        environ={"XDG_DATA_HOME": str(tmp_path / "data"), "XDG_CACHE_HOME": str(tmp_path / "cache")},
    )

    assert paths.app_support_dir == tmp_path / "data" / "MangaCrisp"
    assert paths.cache_dir == tmp_path / "cache" / "MangaCrisp"
    assert paths.default_library_dir == tmp_path / "home" / "MangaCrisp Library"


def test_linux_application_directories_default_to_home(tmp_path: Path) -> None:
    paths = linux_platform.application_directories("MangaCrisp", "RAIV", home=tmp_path, environ={})

    assert paths.app_support_dir == tmp_path / ".local" / "share" / "MangaCrisp"
    assert paths.cache_dir == tmp_path / ".cache" / "MangaCrisp"


def test_linux_open_directory_prefers_xdg_open(tmp_path: Path) -> None:
    with (
        patch.object(linux_platform.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"),
        patch.object(linux_platform.subprocess, "Popen") as popen,
    ):
        linux_platform.open_directory(tmp_path)

    assert popen.call_args.args[0] == ["xdg-open", str(tmp_path)]


def test_linux_open_directory_falls_back_to_gio(tmp_path: Path) -> None:
    def which(name: str) -> str | None:
        return "/usr/bin/gio" if name == "gio" else None

    with (
        patch.object(linux_platform.shutil, "which", side_effect=which),
        patch.object(linux_platform.subprocess, "Popen") as popen,
    ):
        linux_platform.open_directory(tmp_path)

    assert popen.call_args.args[0] == ["gio", "open", str(tmp_path)]


def test_linux_capture_sound_is_silent_without_players() -> None:
    with (
        patch.object(linux_platform.shutil, "which", return_value=None),
        patch.object(linux_platform.subprocess, "Popen") as popen,
    ):
        linux_platform.play_capture_sound()

    popen.assert_not_called()


def test_linux_capture_sound_uses_canberra() -> None:
    with (
        patch.object(linux_platform.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"),
        patch.object(linux_platform.subprocess, "Popen") as popen,
    ):
        linux_platform.play_capture_sound()

    assert popen.call_args.args[0] == ["canberra-gtk-play", "--id", "screen-capture"]
    assert popen.call_args.kwargs["stdout"] is subprocess.DEVNULL


def test_linux_engine_and_subprocess_defaults() -> None:
    assert linux_platform.engine_executable_names("realcugan-ncnn-vulkan") == ("realcugan-ncnn-vulkan",)
    assert linux_platform.subprocess_window_kwargs() == {}


def test_linux_bundled_archive_tools_only_when_frozen(tmp_path: Path) -> None:
    assert linux_platform.bundled_archive_tool_candidates() == ()

    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "executable", str(tmp_path / "MangaCrisp")),
        patch.object(sys, "_MEIPASS", str(tmp_path / "_internal"), create=True),
    ):
        candidates = linux_platform.bundled_archive_tool_candidates()

    assert candidates == (
        tmp_path.resolve() / "tools" / "7zip" / "7zz",
        tmp_path / "_internal" / "tools" / "7zip" / "7zz",
    )
