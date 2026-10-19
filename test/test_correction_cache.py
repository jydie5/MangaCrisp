from __future__ import annotations

import hashlib
import os
from pathlib import Path

from PIL import Image

from mangacrisp_app.correction_cache import (
    CorrectionDiskCache,
    output_cache_source_key,
    page_cache_source_key,
    prune_enhancement_cache,
    remove_enhancement_cache_for_sources,
)


class LazyPages:
    def __init__(self, identities: list[str]) -> None:
        self.identities = identities
        self.indexed = 0

    def __len__(self) -> int:
        return len(self.identities)

    def __getitem__(self, index: int) -> Path:
        self.indexed += 1
        raise AssertionError("lazy provider was materialized")

    def cache_source_identity(self, index: int) -> str:
        return self.identities[index]


def _write_output(cache: CorrectionDiskCache, pages: list[Path], index: int) -> Path:
    output = cache.output_path(pages, index, "scale2_noise0", 2)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"cached")
    return output


def test_legacy_path_identity_and_filename_are_preserved(tmp_path: Path) -> None:
    source = tmp_path / "page one.png"
    Image.new("L", (8, 8), 0).save(source)
    pages = [source]
    cache = CorrectionDiskCache(tmp_path / "cache")

    output = cache.output_path(pages, 0, "scale2_noise0", 2)

    assert output == (
        tmp_path
        / "cache"
        / "interactive"
        / "scale2_noise0"
        / output_cache_source_key(source)
        / "0001_page one_x2.png"
    )


def test_provider_identity_avoids_materialization_and_uses_sha1_key(tmp_path: Path) -> None:
    pages = LazyPages(["pdf:/book.pdf:180:0", "pdf:/book.pdf:180:1"])
    cache = CorrectionDiskCache(tmp_path / "cache")
    expected = hashlib.sha1(pages.identities[1].encode()).hexdigest()[:16]

    output = cache.output_path(pages, 1, "scale3_noise3", 3)

    assert pages.indexed == 0
    assert page_cache_source_key(pages, 1) == expected
    assert output.parent == tmp_path / "cache" / "interactive" / "scale3_noise3" / expected
    assert output.name == "0002_page_x3.png"


def test_path_memo_is_reused_until_explicitly_cleared(tmp_path: Path) -> None:
    pages = LazyPages(["first"])
    cache = CorrectionDiskCache(tmp_path / "cache")

    first = cache.output_path(pages, 0, "settings", 2)
    pages.identities[0] = "changed"
    assert cache.output_path(pages, 0, "settings", 2) == first

    cache.clear_path_memo()
    assert cache.output_path(pages, 0, "settings", 2) != first


def test_cached_path_excludes_active_output_and_touches_once(tmp_path: Path) -> None:
    pages = [tmp_path / "page.png"]
    pages[0].write_bytes(b"source")
    cache = CorrectionDiskCache(tmp_path / "cache")
    output = _write_output(cache, pages, 0)
    old_mtime = 100.0
    os.utime(output, (old_mtime, old_mtime))

    assert cache.cached_path(pages, 0, "scale2_noise0", 2, active_outputs={output}) is None
    loaded = cache.cached_path(pages, 0, "scale2_noise0", 2)
    assert loaded == output
    first_touch_mtime = output.stat().st_mtime_ns
    assert cache.cached_path(pages, 0, "scale2_noise0", 2) == output
    assert output.stat().st_mtime_ns == first_touch_mtime
    assert cache.touched_output_paths == {output}


def test_cached_path_returns_only_existing_inactive_outputs(tmp_path: Path) -> None:
    pages = [tmp_path / "one.png", tmp_path / "two.png"]
    for page in pages:
        page.write_bytes(b"source")
    cache = CorrectionDiskCache(tmp_path / "cache")
    first = _write_output(cache, pages, 0)
    second = cache.output_path(pages, 1, "scale2_noise0", 2)

    assert cache.cached_path(
        pages, 0, "scale2_noise0", 2, active_outputs={first}
    ) is None
    assert cache.cached_path(pages, 1, "scale2_noise0", 2) is None
    second.parent.mkdir(parents=True, exist_ok=True)
    second.write_bytes(b"cached")
    assert cache.cached_path(pages, 0, "scale2_noise0", 2) == first
    assert cache.cached_path(pages, 1, "scale2_noise0", 2) == second


def test_remove_provider_cache_enumerates_identity_without_materializing(tmp_path: Path) -> None:
    pages = LazyPages(["book:0", "book:1"])
    cache_root = tmp_path / "cache"
    parameter_dir = cache_root / "interactive" / "settings"
    for index in range(len(pages)):
        folder = parameter_dir / page_cache_source_key(pages, index)
        folder.mkdir(parents=True)
        (folder / "output.png").write_bytes(b"cached")
    other = parameter_dir / "unrelated"
    other.mkdir()
    (other / "output.png").write_bytes(b"keep")

    removed = remove_enhancement_cache_for_sources(pages, cache_root)

    assert removed == 2
    assert pages.indexed == 0
    assert not (parameter_dir / page_cache_source_key(pages, 0)).exists()
    assert not (parameter_dir / page_cache_source_key(pages, 1)).exists()
    assert (other / "output.png").is_file()


def test_remove_legacy_path_cache_keeps_other_source(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    other = tmp_path / "other.png"
    source.write_bytes(b"source")
    other.write_bytes(b"other")
    cache_root = tmp_path / "cache"
    parameter_dir = cache_root / "interactive" / "settings"
    source_folder = parameter_dir / output_cache_source_key(source)
    other_folder = parameter_dir / output_cache_source_key(other)
    source_folder.mkdir(parents=True)
    other_folder.mkdir(parents=True)
    (source_folder / "output.png").write_bytes(b"remove")
    (other_folder / "output.png").write_bytes(b"keep")

    assert remove_enhancement_cache_for_sources([source], cache_root) == 1
    assert not source_folder.exists()
    assert other_folder.is_dir()


def test_prune_uses_limit_age_and_protected_paths(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    protected = cache_root / "interactive" / "settings" / "active" / "active.png"
    expired = cache_root / "interactive" / "settings" / "old" / "old.png"
    for path in (protected, expired):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"1234")
    os.utime(protected, (900.0, 900.0))
    os.utime(expired, (100.0, 100.0))

    removed = prune_enhancement_cache(
        cache_root,
        max_bytes=1,
        max_age_seconds=500,
        protected={protected.parent},
        now=1_000.0,
    )

    assert removed == 1
    assert protected.is_file()
    assert not expired.exists()


def test_cache_prune_protects_active_output_parent_for_staging(tmp_path: Path) -> None:
    cache = CorrectionDiskCache(tmp_path / "cache", limit_bytes=1, max_age_seconds=None)
    active = cache.output_path([tmp_path / "page.png"], 0, "settings", 2)
    active.parent.mkdir(parents=True, exist_ok=True)
    staging = active.parent / ".mangacrisp-page-staging"
    staging.mkdir()
    removed = cache.prune(active_outputs={active}, now=1_000.0)

    assert removed == 0
    assert staging.is_dir()
