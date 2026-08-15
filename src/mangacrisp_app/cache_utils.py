from __future__ import annotations

import time
from pathlib import Path


def prune_png_cache(
    cache_root: Path,
    *,
    max_bytes: int,
    max_age_seconds: int | None = None,
    protected: set[Path] | None = None,
    now: float | None = None,
) -> int:
    """Remove expired and least-recently-used PNG cache files."""
    root = cache_root.expanduser()
    if not root.is_dir():
        return 0

    protected_paths = {_resolved(path) for path in protected or set()}
    entries: list[tuple[float, int, Path]] = []
    total = 0
    for path in root.rglob("*.png"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        total += stat.st_size
        entries.append((stat.st_mtime, stat.st_size, path))

    removed = 0
    cutoff = None
    if max_age_seconds is not None:
        cutoff = (time.time() if now is None else now) - max(0, max_age_seconds)

    remaining: list[tuple[float, int, Path]] = []
    for mtime, size, path in sorted(entries):
        if cutoff is None or mtime >= cutoff or _resolved(path) in protected_paths:
            remaining.append((mtime, size, path))
            continue
        if _remove_file(path):
            total -= size
            removed += 1

    for _mtime, size, path in remaining:
        if total <= max(0, max_bytes):
            break
        if _resolved(path) in protected_paths:
            continue
        if _remove_file(path):
            total -= size
            removed += 1

    _remove_empty_directories(root)
    return removed


def _resolved(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser().absolute()


def _remove_file(path: Path) -> bool:
    try:
        path.unlink()
    except OSError:
        return False
    return True


def _remove_empty_directories(root: Path) -> None:
    directories = [path for path in root.rglob("*") if path.is_dir()]
    for directory in sorted(
        directories, key=lambda path: len(path.parts), reverse=True
    ):
        try:
            directory.rmdir()
        except OSError:
            pass
