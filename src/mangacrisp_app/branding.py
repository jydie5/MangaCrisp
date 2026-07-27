from __future__ import annotations

from mangacrisp_app.platform import application_directories


APP_NAME = "MangaCrisp"
APP_BUNDLE_IDENTIFIER = "com.jydie5.mangacrisp"
PROJECT_URL = "https://github.com/jydie5/MangaCrisp"
SUPPORT_URL = "https://buymeacoffee.com/jydie5"

_DIRECTORIES = application_directories(APP_NAME, "RAIV")
APP_SUPPORT_DIR = _DIRECTORIES.app_support_dir
CACHE_DIR = _DIRECTORIES.cache_dir
DEFAULT_LIBRARY_DIR = _DIRECTORIES.default_library_dir

LEGACY_APP_SUPPORT_DIR = _DIRECTORIES.legacy_app_support_dir
LEGACY_CACHE_DIR = _DIRECTORIES.legacy_cache_dir
LEGACY_DEFAULT_LIBRARY_DIR = _DIRECTORIES.legacy_default_library_dir
