from __future__ import annotations

from pathlib import Path


APP_NAME = "MangaCrisp"
APP_BUNDLE_IDENTIFIER = "com.jydie5.mangacrisp"
PROJECT_URL = "https://github.com/jydie5/MangaCrisp"
SUPPORT_URL = "https://buymeacoffee.com/jydie5"

APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
CACHE_DIR = Path.home() / "Library" / "Caches" / APP_NAME
DEFAULT_LIBRARY_DIR = Path.home() / f"{APP_NAME} Library"

LEGACY_APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "RAIV"
LEGACY_CACHE_DIR = Path.home() / "Library" / "Caches" / "RAIV"
LEGACY_DEFAULT_LIBRARY_DIR = Path.home() / "RAIV Library"
