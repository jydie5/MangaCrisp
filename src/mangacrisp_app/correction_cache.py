"""Disk paths and lifecycle helpers for AI correction output.

The reader owns when a page should be processed.  This module owns the
stable, UI-independent mapping from a page to its disposable correction cache
and the small amount of session state needed while reading.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Collection, Sequence
from hashlib import sha1
from pathlib import Path

from mangacrisp_app.branding import CACHE_DIR
from mangacrisp_app.cache_utils import prune_png_cache

ROOT_DIR = Path(__file__).resolve().parents[2]


def default_upscale_dir() -> Path:
    """Return the application correction-cache root for this runtime."""
    if getattr(sys, "frozen", False):
        return CACHE_DIR / "upscale"
    return ROOT_DIR / "test" / "output" / "upscale"


DEFAULT_UPSCALE_DIR = default_upscale_dir()
AI_ENHANCEMENT_CACHE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
AI_ENHANCEMENT_CACHE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def _source_fingerprint(source: Path) -> str:
    """Return the legacy path/size/mtime identity for an image file."""
    try:
        stat = source.stat()
        identity = f"{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    except OSError:
        identity = str(source.expanduser())
    return identity


def output_cache_source_key(source: Path) -> str:
    """Return the legacy 16-character key for a materialized image path."""
    return sha1(_source_fingerprint(source).encode("utf-8")).hexdigest()[:16]


def _provider_identity(pages: object, index: int) -> str | None:
    identity_method = getattr(pages, "cache_source_identity", None)
    if not callable(identity_method):
        return None
    return identity_method(index)


def _identity_key(identity: str) -> str:
    return sha1(identity.encode("utf-8")).hexdigest()[:16]


def page_cache_source_key(pages: object, index: int) -> str:
    """Return a page key without materializing provider-backed pages when possible."""
    identity = _provider_identity(pages, index)
    if identity is not None:
        return _identity_key(identity)
    source = pages[index]  # type: ignore[index]
    return output_cache_source_key(Path(source))


class CorrectionDiskCache:
    """Map reader pages to correction files and manage disposable cache access.

    ``pages`` may be a normal sequence of image paths or a lazy provider.  A
    provider that implements ``cache_source_identity(index)`` is queried for
    its stable identity and is never indexed by this class merely to construct
    a cache path.  This keeps PDF and archive providers lazy across restarts.
    """

    def __init__(
        self,
        cache_root: Path = DEFAULT_UPSCALE_DIR,
        *,
        limit_bytes: int = AI_ENHANCEMENT_CACHE_LIMIT_BYTES,
        max_age_seconds: int | None = AI_ENHANCEMENT_CACHE_MAX_AGE_SECONDS,
    ) -> None:
        self.cache_root = Path(cache_root).expanduser().resolve()
        self.limit_bytes = max(0, int(limit_bytes))
        self.max_age_seconds = None if max_age_seconds is None else max(0, int(max_age_seconds))
        self._memo_pages: object | None = None
        self.path_memo: dict[tuple[int, str, int], Path] = {}
        self.touched_output_paths: set[Path] = set()

    def output_path(
        self,
        pages: object,
        index: int,
        parameter_key: str,
        scale: int,
    ) -> Path:
        """Return a memoized output path for one page and correction setting."""
        if index < 0:
            raise IndexError(index)
        if pages is not self._memo_pages:
            self.clear_path_memo()
            self._memo_pages = pages
        memo_key = (index, str(parameter_key), int(scale))
        cached = self.path_memo.get(memo_key)
        if cached is not None:
            return cached

        identity_method = getattr(pages, "cache_source_identity", None)
        identity = _provider_identity(pages, index)
        if callable(identity_method) and identity is not None:
            source_key = _identity_key(identity)
            source_stem = "page"
        else:
            source = Path(pages[index])  # type: ignore[index]
            source_key = output_cache_source_key(source)
            source_stem = source.stem
        folder = self.cache_root / "interactive" / str(parameter_key) / source_key
        output = folder / f"{index + 1:04d}_{source_stem}_x{int(scale)}.png"
        self.path_memo[memo_key] = output
        return output

    def clear_path_memo(self) -> None:
        """Forget page-path mappings after a provider/source identity changes."""
        self.path_memo.clear()

    def cached_path(
        self,
        pages: object,
        index: int,
        parameter_key: str,
        scale: int,
        *,
        active_outputs: Collection[Path] | None = None,
    ) -> Path | None:
        """Return an existing, inactive output and touch it once per session."""
        output = self.output_path(pages, index, parameter_key, scale)
        active = active_outputs or ()
        if output in active or not output.is_file():
            return None
        if output not in self.touched_output_paths:
            try:
                os.utime(output, None)
            except OSError:
                return None
            self.touched_output_paths.add(output)
        return output

    def prune(
        self,
        *,
        protected: Collection[Path] | None = None,
        active_outputs: Collection[Path] | None = None,
        now: float | None = None,
    ) -> int:
        """Prune correction PNGs through the shared generic cache utility."""
        protected_paths = {Path(path) for path in protected or ()}
        for active in active_outputs or ():
            active_path = Path(active)
            protected_paths.add(active_path)
            protected_paths.add(active_path.parent)
        return prune_png_cache(
            self.cache_root,
            max_bytes=self.limit_bytes,
            max_age_seconds=self.max_age_seconds,
            protected=protected_paths,
            now=now,
        )


def remove_enhancement_cache_for_sources(
    sources: Sequence[Path],
    cache_root: Path | None = None,
) -> int:
    """Delete correction folders for paths or a lazy page provider.

    When ``sources`` exposes
    ``cache_source_identity(index)``, only ``range(len(sources))`` is enumerated;
    no page image is materialized while discovering deletion keys.
    """
    interactive_root = (cache_root or DEFAULT_UPSCALE_DIR) / "interactive"
    if not interactive_root.is_dir():
        return 0

    identity_method = getattr(sources, "cache_source_identity", None)
    if callable(identity_method):
        keys = {page_cache_source_key(sources, index) for index in range(len(sources))}
    else:
        keys = {output_cache_source_key(Path(source)) for source in sources}

    removed = 0
    for parameter_dir in interactive_root.iterdir():
        if not parameter_dir.is_dir():
            continue
        for key in keys:
            target_dir = parameter_dir / key
            if target_dir.is_dir():
                shutil.rmtree(target_dir, ignore_errors=True)
                removed += 1
    return removed


def prune_enhancement_cache(
    cache_root: Path | None = None,
    *,
    max_bytes: int = AI_ENHANCEMENT_CACHE_LIMIT_BYTES,
    max_age_seconds: int | None = AI_ENHANCEMENT_CACHE_MAX_AGE_SECONDS,
    protected: Collection[Path] | None = None,
    now: float | None = None,
) -> int:
    """Prune correction PNGs with the shared generic cache implementation."""
    return prune_png_cache(
        cache_root or DEFAULT_UPSCALE_DIR,
        max_bytes=max_bytes,
        max_age_seconds=max_age_seconds,
        protected={Path(path) for path in protected or ()},
        now=now,
    )


__all__ = [
    "AI_ENHANCEMENT_CACHE_LIMIT_BYTES",
    "AI_ENHANCEMENT_CACHE_MAX_AGE_SECONDS",
    "DEFAULT_UPSCALE_DIR",
    "CorrectionDiskCache",
    "default_upscale_dir",
    "output_cache_source_key",
    "page_cache_source_key",
    "prune_enhancement_cache",
    "remove_enhancement_cache_for_sources",
]
