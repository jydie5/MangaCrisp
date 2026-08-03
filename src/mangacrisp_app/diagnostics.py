from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import platform
import plistlib
import sys
from pathlib import Path

from mangacrisp_app.engine_utils import realcugan_executable


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def module_version(module_name: str, attribute: str = "__version__") -> str:
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return "not installed"
    value = getattr(module, attribute, None)
    return str(value) if value is not None else package_version(module_name)


def app_version() -> str:
    version = package_version("mangacrisp")
    if version != "not installed":
        return version
    if not getattr(sys, "frozen", False):
        return version
    info_path = Path(sys.executable).resolve().parents[1] / "Info.plist"
    try:
        with info_path.open("rb") as handle:
            info = plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException):
        return "unknown"
    return str(info.get("CFBundleShortVersionString") or "unknown")


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    for item in path.rglob("*"):
        if not item.is_file() or item.is_symlink():
            continue
        try:
            total += item.stat().st_size
        except OSError:
            continue
    return total


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def diagnostics_text(*, book_count: int, cache_dir: Path) -> str:
    engine = realcugan_executable()
    engine_hash = "unavailable"
    if engine is not None and engine.is_file():
        try:
            engine_hash = sha256_file(engine)
        except OSError:
            engine_hash = "unreadable"
    lines = [
        "MangaCrisp diagnostics",
        f"app_version: {app_version()}",
        f"os: {platform.system()} {platform.release()}",
        f"machine: {platform.machine()}",
        f"python: {platform.python_version()} frozen={bool(getattr(sys, 'frozen', False))}",
        f"pyside6: {module_version('PySide6')}",
        f"pillow: {module_version('PIL')}",
        f"pypdfium2: {module_version('pypdfium2', 'PYPDFIUM_INFO')}",
        f"realcugan_available: {engine is not None}",
        f"realcugan_sha256: {engine_hash}",
        f"bookshelf_items: {book_count}",
        f"cache_bytes: {directory_size(cache_dir)}",
    ]
    return "\n".join(lines) + "\n"
