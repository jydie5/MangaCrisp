from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from mangacrisp_app.platform.common import application_directories

__all__ = [
    "application_directories",
    "bundled_archive_tool_candidates",
    "engine_executable_names",
    "open_directory",
    "play_capture_sound",
    "subprocess_window_kwargs",
]

CAPTURE_SOUND_ID = "screen-capture"
CAPTURE_SOUND_FILES = (
    Path("/usr/share/sounds/freedesktop/stereo/screen-capture.oga"),
    Path("/usr/share/sounds/freedesktop/stereo/camera-shutter.oga"),
)


def open_directory(path: Path) -> None:
    for command in (["xdg-open"], ["gio", "open"]):
        if shutil.which(command[0]):
            subprocess.Popen(
                [*command, str(path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
    raise FileNotFoundError("xdg-open or gio is required to open directories")


def play_capture_sound() -> None:
    quiet = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if shutil.which("canberra-gtk-play"):
        subprocess.Popen(["canberra-gtk-play", "--id", CAPTURE_SOUND_ID], **quiet)
        return
    player = shutil.which("pw-play") or shutil.which("paplay")
    sound = next((path for path in CAPTURE_SOUND_FILES if path.is_file()), None)
    if player and sound:
        subprocess.Popen([player, str(sound)], **quiet)


def subprocess_window_kwargs() -> dict[str, int]:
    return {}


def engine_executable_names(base_name: str) -> tuple[str, ...]:
    return (base_name,)


def bundled_archive_tool_candidates() -> tuple[Path, ...]:
    if not getattr(sys, "frozen", False):
        return ()
    roots = [Path(sys.executable).resolve().parent]
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    return tuple(root / "tools" / "7zip" / "7zz" for root in roots)
