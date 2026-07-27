from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from mangacrisp_app.platform.common import ApplicationDirectories


def application_directories(
    app_name: str,
    legacy_app_name: str,
    *,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> ApplicationDirectories:
    del environ
    user_home = home or Path.home()
    return ApplicationDirectories(
        app_support_dir=user_home / "Library" / "Application Support" / app_name,
        cache_dir=user_home / "Library" / "Caches" / app_name,
        default_library_dir=user_home / f"{app_name} Library",
        legacy_app_support_dir=user_home / "Library" / "Application Support" / legacy_app_name,
        legacy_cache_dir=user_home / "Library" / "Caches" / legacy_app_name,
        legacy_default_library_dir=user_home / f"{legacy_app_name} Library",
    )


def open_directory(path: Path) -> None:
    subprocess.Popen(["open", str(path)])


def subprocess_window_kwargs() -> dict[str, int]:
    return {}


def engine_executable_names(base_name: str) -> tuple[str, ...]:
    return (base_name,)
