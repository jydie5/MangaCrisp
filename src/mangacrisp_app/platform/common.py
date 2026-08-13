from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApplicationDirectories:
    app_support_dir: Path
    cache_dir: Path
    default_library_dir: Path
    legacy_app_support_dir: Path
    legacy_cache_dir: Path
    legacy_default_library_dir: Path


def application_directories(
    app_name: str,
    legacy_app_name: str,
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> ApplicationDirectories:
    user_home = home or Path.home()
    environment = os.environ if environ is None else environ
    data_home = Path(environment.get("XDG_DATA_HOME", user_home / ".local" / "share"))
    cache_home = Path(environment.get("XDG_CACHE_HOME", user_home / ".cache"))
    return ApplicationDirectories(
        app_support_dir=data_home / app_name,
        cache_dir=cache_home / app_name,
        default_library_dir=user_home / f"{app_name} Library",
        legacy_app_support_dir=data_home / legacy_app_name,
        legacy_cache_dir=cache_home / legacy_app_name,
        legacy_default_library_dir=user_home / f"{legacy_app_name} Library",
    )


def open_directory(path: Path) -> None:
    subprocess.Popen(["xdg-open", str(path)])


def play_capture_sound() -> None:
    pass


def subprocess_window_kwargs() -> dict[str, int]:
    return {}


def engine_executable_names(base_name: str) -> tuple[str, ...]:
    return (base_name,)


def bundled_archive_tool_candidates() -> tuple[Path, ...]:
    return ()
