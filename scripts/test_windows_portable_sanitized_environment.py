from __future__ import annotations

import argparse
import importlib.metadata
import os
import subprocess
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from mangacrisp_app.platform import subprocess_window_kwargs

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = (
    ROOT_DIR
    / "dist"
    / f"MangaCrisp-{importlib.metadata.version('mangacrisp')}-windows-x64-portable-baseline.zip"
)
REMOVED_ENVIRONMENT_KEYS = {
    "CONDA_PREFIX",
    "PYTHONHOME",
    "PYTHONPATH",
    "UV",
    "UV_PROJECT",
    "UV_PROJECT_ENVIRONMENT",
    "VIRTUAL_ENV",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke-test an extracted Windows portable ZIP without Python, uv, "
            "or virtual-environment paths."
        )
    )
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    return parser.parse_args()


def safe_extract(archive_path: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            target = (destination / info.filename).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"unsafe ZIP member: {info.filename}")
        archive.extractall(destination)


def sanitized_environment(profile: Path) -> dict[str, str]:
    environment = os.environ.copy()
    for key in REMOVED_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    system_root = Path(environment.get("SystemRoot", r"C:\Windows"))
    environment.update(
        {
            "APPDATA": str(profile / "AppData" / "Roaming"),
            "LOCALAPPDATA": str(profile / "AppData" / "Local"),
            "MANGACRISP_LANGUAGE": "en",
            "PATH": os.pathsep.join((str(system_root / "System32"), str(system_root))),
            "QT_QPA_PLATFORM": "offscreen",
            "USERPROFILE": str(profile),
        }
    )
    return environment


def main() -> None:
    args = parse_args()
    archive_path = args.archive.resolve()
    if not archive_path.is_file():
        raise SystemExit(f"portable ZIP was not found: {archive_path}")

    with TemporaryDirectory(prefix="mangacrisp-sanitized-environment-") as temporary:
        root = Path(temporary)
        safe_extract(archive_path, root)
        app_dir = root / "MangaCrisp"
        executable = app_dir / "MangaCrisp.exe"
        if not executable.is_file():
            raise SystemExit(f"portable ZIP is missing: {executable.name}")
        environment = sanitized_environment(root / "profile")
        completed = subprocess.run(
            [str(executable), "--smoke-test"],
            cwd=app_dir,
            env=environment,
            check=False,
            timeout=30,
            **subprocess_window_kwargs(),
        )
        if completed.returncode != 0:
            raise SystemExit(
                f"sanitized-environment smoke test failed: {completed.returncode}"
            )

    print(f"archive: {archive_path}")
    print("sanitized_environment_smoke=passed")
    print(r"path=C:\Windows\System32;C:\Windows")
    print("python_uv_virtualenv_removed=true")
    print("note=this is not a substitute for a separate clean Windows account test")


if __name__ == "__main__":
    main()
