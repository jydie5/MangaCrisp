from __future__ import annotations

import configparser
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from mangacrisp_app.branding import APP_BUNDLE_IDENTIFIER

ROOT_DIR = Path(__file__).resolve().parents[1]
PACKAGING_DIR = ROOT_DIR / "packaging" / "linux"
DESKTOP_FILE = PACKAGING_DIR / f"{APP_BUNDLE_IDENTIFIER}.desktop"

SPEC = importlib.util.spec_from_file_location("fetch_7zip_linux", ROOT_DIR / "scripts" / "fetch_7zip_linux.py")
assert SPEC is not None and SPEC.loader is not None
fetch_7zip_linux = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_7zip_linux)


def read_desktop_entry() -> configparser.SectionProxy:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # type: ignore[assignment]
    parser.read(DESKTOP_FILE, encoding="utf-8")
    return parser["Desktop Entry"]


def test_desktop_entry_matches_application_id() -> None:
    entry = read_desktop_entry()

    assert entry["Icon"] == APP_BUNDLE_IDENTIFIER
    assert entry["StartupWMClass"] == APP_BUNDLE_IDENTIFIER
    assert entry["Exec"] == '"@EXEC@" %f'
    assert "application/vnd.comicbook+zip" in entry["MimeType"].split(";")


def test_7zip_pin_is_official_linux_release() -> None:
    assert fetch_7zip_linux.ARCHIVE_URL == (
        "https://github.com/ip7z/7zip/releases/download/26.02/7z2602-linux-x64.tar.xz"
    )
    assert set(fetch_7zip_linux.FILE_SHA256) == {"7zz", "License.txt", "readme.txt"}


def test_7zip_verification_requires_pinned_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in fetch_7zip_linux.FILE_SHA256:
        (tmp_path / name).write_text(name, encoding="utf-8")
    assert fetch_7zip_linux.verify_tool_directory(tmp_path) is False

    monkeypatch.setattr(
        fetch_7zip_linux,
        "FILE_SHA256",
        {name: fetch_7zip_linux.sha256_file(tmp_path / name) for name in fetch_7zip_linux.FILE_SHA256},
    )
    assert fetch_7zip_linux.verify_tool_directory(tmp_path) is True


def make_fake_build(root: Path) -> Path:
    app = root / "MangaCrisp"
    (app / "share").mkdir(parents=True)
    executable = app / "MangaCrisp"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    shutil.copy2(DESKTOP_FILE, app / "share" / DESKTOP_FILE.name)
    for size in (256, 512):
        icon = app / "share" / "icons" / f"{size}x{size}" / f"{APP_BUNDLE_IDENTIFIER}.png"
        icon.parent.mkdir(parents=True)
        icon.write_bytes(b"png")
    for script in ("install.sh", "uninstall.sh"):
        shutil.copy2(PACKAGING_DIR / script, app / script)
    return app


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell installer")
def test_install_and_uninstall_for_current_user(tmp_path: Path) -> None:
    app = make_fake_build(tmp_path / "download")
    home = tmp_path / "home"
    environment = {"HOME": str(home), "PATH": os.environ["PATH"]}

    subprocess.run(["sh", str(app / "install.sh")], env=environment, check=True, capture_output=True)

    installed = home / ".local" / "opt" / "MangaCrisp"
    desktop = home / ".local" / "share" / "applications" / f"{APP_BUNDLE_IDENTIFIER}.desktop"
    assert (installed / "MangaCrisp").is_file()
    assert f'Exec="{installed}/MangaCrisp" %f' in desktop.read_text(encoding="utf-8")
    assert (home / ".local" / "bin" / "mangacrisp").resolve() == (installed / "MangaCrisp").resolve()
    assert (
        home / ".local" / "share" / "icons" / "hicolor" / "512x512" / "apps" / f"{APP_BUNDLE_IDENTIFIER}.png"
    ).is_file()

    library = home / "MangaCrisp Library"
    library.mkdir()
    subprocess.run(["sh", str(installed / "uninstall.sh")], env=environment, check=True, capture_output=True)

    assert not installed.exists()
    assert not desktop.exists()
    assert not (home / ".local" / "bin" / "mangacrisp").exists()
    assert library.is_dir()
