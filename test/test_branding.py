from __future__ import annotations

import json
from pathlib import Path

from raiv_app.branding import APP_BUNDLE_IDENTIFIER, APP_NAME, PROJECT_URL
from raiv_app.library import migrate_legacy_application_state


def test_public_branding_constants() -> None:
    assert APP_NAME == "MangaCrisp"
    assert APP_BUNDLE_IDENTIFIER == "com.jydie5.mangacrisp"
    assert PROJECT_URL == "https://github.com/jydie5/MangaCrisp"


def test_legacy_state_migration_preserves_settings_and_cache(tmp_path: Path) -> None:
    legacy_support = tmp_path / "Application Support" / "RAIV"
    current_support = tmp_path / "Application Support" / "MangaCrisp"
    legacy_cache = tmp_path / "Caches" / "RAIV"
    current_cache = tmp_path / "Caches" / "MangaCrisp"
    legacy_support.mkdir(parents=True)
    legacy_cache.mkdir(parents=True)
    (legacy_support / "settings.json").write_text(
        json.dumps({"library_dir": str(tmp_path / "RAIV Library")}),
        encoding="utf-8",
    )
    (legacy_support / "raiv.sqlite3").write_bytes(b"database")
    (legacy_cache / "enhanced.png").write_bytes(b"cache")

    migrate_legacy_application_state(
        current_support,
        legacy_app_support=legacy_support,
        cache_dir=current_cache,
        legacy_cache_dir=legacy_cache,
    )

    assert (current_support / "settings.json").is_file()
    assert (current_support / "mangacrisp.sqlite3").read_bytes() == b"database"
    assert not (current_support / "raiv.sqlite3").exists()
    assert (current_cache / "enhanced.png").read_bytes() == b"cache"


def test_legacy_state_does_not_overwrite_existing_state(tmp_path: Path) -> None:
    legacy_support = tmp_path / "legacy"
    current_support = tmp_path / "current"
    legacy_cache = tmp_path / "legacy-cache"
    current_cache = tmp_path / "current-cache"
    legacy_support.mkdir()
    current_support.mkdir()
    (legacy_support / "settings.json").write_text("legacy", encoding="utf-8")
    (current_support / "settings.json").write_text("current", encoding="utf-8")

    migrate_legacy_application_state(
        current_support,
        legacy_app_support=legacy_support,
        cache_dir=current_cache,
        legacy_cache_dir=legacy_cache,
    )

    assert (current_support / "settings.json").read_text(encoding="utf-8") == "current"
