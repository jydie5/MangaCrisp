from __future__ import annotations

import os
from pathlib import Path

from mangacrisp_app.cache_utils import prune_png_cache
from mangacrisp_app.library import cleanup_interrupted_import_storage


def test_png_cache_prunes_expired_files_and_empty_directories(tmp_path: Path) -> None:
    expired = tmp_path / "old" / "expired.png"
    current = tmp_path / "current.png"
    expired.parent.mkdir()
    expired.write_bytes(b"old")
    current.write_bytes(b"new")
    os.utime(expired, (100.0, 100.0))
    os.utime(current, (900.0, 900.0))

    removed = prune_png_cache(
        tmp_path,
        max_bytes=100,
        max_age_seconds=500,
        now=1_000.0,
    )

    assert removed == 1
    assert not expired.exists()
    assert not expired.parent.exists()
    assert current.read_bytes() == b"new"


def test_png_cache_prunes_oldest_files_to_size_and_preserves_active_file(
    tmp_path: Path,
) -> None:
    oldest = tmp_path / "oldest.png"
    active = tmp_path / "active.png"
    newest = tmp_path / "newest.png"
    for path, modified in ((oldest, 100.0), (active, 200.0), (newest, 300.0)):
        path.write_bytes(b"1234")
        os.utime(path, (modified, modified))

    removed = prune_png_cache(
        tmp_path,
        max_bytes=4,
        max_age_seconds=None,
        protected={active},
    )

    assert removed == 2
    assert active.exists()
    assert not oldest.exists()
    assert not newest.exists()


def test_interrupted_import_cleanup_restores_backup_and_removes_staging(
    tmp_path: Path,
) -> None:
    library = tmp_path / "Library"
    library.mkdir()
    staging = library / f".Volume 1.import-{'1' * 32}"
    backup = library / f".Volume 1.backup-{'2' * 32}"
    unrelated = library / ".keep-me"
    staging.mkdir()
    backup.mkdir()
    unrelated.mkdir()
    (staging / "partial.png").write_bytes(b"partial")
    (backup / "preserved.png").write_bytes(b"preserved")

    removed, restored = cleanup_interrupted_import_storage(library)

    assert (removed, restored) == (1, 1)
    assert not staging.exists()
    assert not backup.exists()
    assert (library / "Volume 1" / "preserved.png").read_bytes() == b"preserved"
    assert unrelated.exists()


def test_interrupted_import_cleanup_discards_backup_when_target_exists(
    tmp_path: Path,
) -> None:
    library = tmp_path / "Library"
    target = library / "Volume 1"
    backup = library / f".Volume 1.backup-{'3' * 32}"
    target.mkdir(parents=True)
    backup.mkdir()
    (target / "current.png").write_bytes(b"current")
    (backup / "old.png").write_bytes(b"old")

    removed, restored = cleanup_interrupted_import_storage(library)

    assert (removed, restored) == (1, 0)
    assert (target / "current.png").read_bytes() == b"current"
    assert not backup.exists()
