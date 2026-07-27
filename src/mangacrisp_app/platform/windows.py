from __future__ import annotations

import os
import subprocess
import sys
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
    user_home = home or Path.home()
    environment = os.environ if environ is None else environ
    roaming_root = Path(environment.get("APPDATA", user_home / "AppData" / "Roaming"))
    local_root = Path(environment.get("LOCALAPPDATA", user_home / "AppData" / "Local"))
    return ApplicationDirectories(
        app_support_dir=roaming_root / app_name,
        cache_dir=local_root / app_name,
        default_library_dir=user_home / f"{app_name} Library",
        legacy_app_support_dir=roaming_root / legacy_app_name,
        legacy_cache_dir=local_root / legacy_app_name,
        legacy_default_library_dir=user_home / f"{legacy_app_name} Library",
    )


def open_directory(path: Path) -> None:
    os.startfile(str(path))


def subprocess_window_kwargs() -> dict[str, int]:
    creation_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {"creationflags": creation_flag} if creation_flag else {}


def engine_executable_names(base_name: str) -> tuple[str, ...]:
    return (f"{base_name}.exe", base_name)


def bundled_archive_tool_candidates() -> tuple[Path, ...]:
    roots = [Path(sys.executable).resolve().parent]
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    return tuple(
        root / "tools" / "7zip" / executable_name
        for root in roots
        for executable_name in ("7z.exe", "7zz.exe")
    )
