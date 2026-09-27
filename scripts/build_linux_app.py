from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

from fetch_7zip_linux import ensure_7zip
from fetch_7zip_linux import write_provenance as write_7zip_provenance
from fetch_realcugan_linux import (
    download_verified,
    ensure_realcugan,
    fetch_license_files,
)
from fetch_realcugan_linux import write_provenance as write_realcugan_provenance
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT_DIR / "src" / "mangacrisp_app" / "main.py"
APP_ID = "com.jydie5.mangacrisp"
APP_ICON_SOURCE = ROOT_DIR / "assets" / "mangacrisp-app-icon.png"
PACKAGING_DIR = ROOT_DIR / "packaging" / "linux"
BUILD_DIR = ROOT_DIR / "build" / "linux"
VENDOR_DIR = ROOT_DIR / "build" / "vendor"
LICENSES_DIR = BUILD_DIR / "licenses"
DIST_DIR = ROOT_DIR / "dist"
DIST_APP = DIST_DIR / "MangaCrisp"
DIST_EXECUTABLE = DIST_APP / "MangaCrisp"
ICON_SIZES = (256, 512)
RUNTIME_DISTRIBUTIONS = (
    "PyInstaller",
    "setuptools",
    "packaging",
    "PySide6",
    "shiboken6",
    "Pillow",
    "py7zr",
    "backports-zstd",
    "brotli",
    "inflate64",
    "multivolumefile",
    "psutil",
    "pybcj",
    "pycryptodomex",
    "pyppmd",
    "texttable",
    "rarfile",
    "pypdfium2",
    "jeepney",
)
# Linux PySide6/shiboken6 wheels carry no license files; the pinned LGPL text
# below covers them, as in the macOS build.
QT_DISTRIBUTIONS = {"PySide6", "shiboken6"}
QT_LICENSE_NAME = "Qt-PySide6-LGPL-3.0-only.txt"
QT_LICENSE_URL = (
    "https://raw.githubusercontent.com/qtproject/pyside-pyside-setup/v6.11.1/LICENSES/LGPL-3.0-only.txt"
)
QT_LICENSE_SHA256 = "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768"


def project_version() -> str:
    return importlib.metadata.version("mangacrisp")


def archive_path() -> Path:
    return DIST_DIR / f"MangaCrisp-{project_version()}-linux-x86_64.tar.gz"


def copy_distribution_licenses(destination: Path) -> int:
    copied = 0
    for package_name in RUNTIME_DISTRIBUTIONS:
        try:
            distribution = importlib.metadata.distribution(package_name)
        except importlib.metadata.PackageNotFoundError:
            # Optional transitive dependencies differ between Python versions.
            if package_name in {"backports-zstd", "setuptools"}:
                continue
            raise
        sources = [
            Path(distribution.locate_file(relative_path))
            for relative_path in distribution.files or []
            if ".dist-info" in str(relative_path)
            and any(term in str(relative_path).lower() for term in ("license", "copying", "notice"))
        ]
        sources = [source for source in sources if source.is_file()]
        if not sources and package_name in QT_DISTRIBUTIONS:
            continue
        if not sources:
            raise RuntimeError(f"no license file found for runtime dependency: {package_name}")
        for index, source in enumerate(sources, start=1):
            suffix = "" if len(sources) == 1 else f"-{index}"
            filename = f"Python-{package_name}-{distribution.version}{suffix}-{source.name}"
            shutil.copy2(source, destination / filename)
            copied += 1
    return copied


def copy_python_license(destination: Path) -> Path:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = (
        Path(sys.base_prefix) / "lib" / version / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "share" / "doc" / version / "copyright",
        Path("/usr/share/doc") / version / "copyright",
    )
    source = next((path for path in candidates if path.is_file()), None)
    if source is None:
        raise RuntimeError(f"Python runtime license was not found under {sys.base_prefix}")
    target = destination / f"Python-{platform.python_version()}-{source.name}"
    shutil.copy2(source, target)
    return target


def write_qt_source_notice(destination: Path) -> None:
    pyside_version = importlib.metadata.version("PySide6")
    (destination / "Qt-PySide6-source-and-relinking.txt").write_text(
        "MangaCrisp uses PySide6 and Qt under the LGPL v3 option.\n\n"
        f"Bundled PySide6 version: {pyside_version}\n"
        f"PySide6 source: https://github.com/qtproject/pyside-pyside-setup/tree/v{pyside_version}\n"
        f"Qt source: https://github.com/qt/qtbase/tree/v{pyside_version}\n"
        "MangaCrisp application source: https://github.com/jydie5/MangaCrisp\n\n"
        "The dynamically linked Qt libraries are stored under:\n"
        "MangaCrisp/_internal/PySide6/Qt/lib/\n\n"
        "Compatible Qt/PySide6 shared libraries may be replaced for relinking.\n"
        f"The complete LGPL v3 text is included as {QT_LICENSE_NAME}.\n",
        encoding="utf-8",
    )


def prepare_license_files(archive_tool_dir: Path | None, engine_dir: Path | None) -> Path:
    shutil.rmtree(LICENSES_DIR, ignore_errors=True)
    LICENSES_DIR.mkdir(parents=True)
    shutil.copy2(ROOT_DIR / "LICENSE", LICENSES_DIR / "MangaCrisp-MIT.txt")
    shutil.copy2(ROOT_DIR / "THIRD_PARTY_NOTICES.md", LICENSES_DIR / "THIRD_PARTY_NOTICES.md")
    copy_distribution_licenses(LICENSES_DIR)
    copy_python_license(LICENSES_DIR)
    write_qt_source_notice(LICENSES_DIR)
    download_verified(QT_LICENSE_URL, LICENSES_DIR / QT_LICENSE_NAME, QT_LICENSE_SHA256)
    if archive_tool_dir is not None:
        shutil.copy2(archive_tool_dir / "License.txt", LICENSES_DIR / "7-Zip-License.txt")
        shutil.copy2(archive_tool_dir / "readme.txt", LICENSES_DIR / "7-Zip-readme.txt")
        write_7zip_provenance(LICENSES_DIR, archive_tool_dir)
    if engine_dir is not None:
        shutil.copy2(engine_dir / "LICENSE", LICENSES_DIR / "realcugan-ncnn-vulkan-MIT.txt")
        fetch_license_files(LICENSES_DIR)
        write_realcugan_provenance(LICENSES_DIR, engine_dir)
    archive_summary = (
        "The pinned 7-Zip console binary (7zz) is bundled for RAR/CBR fallback extraction.\n"
        if archive_tool_dir is not None
        else "The 7-Zip archive backend is omitted from this diagnostic build.\n"
    )
    engine_summary = (
        "The official Real-CUGAN ncnn Vulkan Ubuntu engine and models are bundled "
        "unmodified. It uses the system Vulkan loader and libgomp.\n"
        if engine_dir is not None
        else "Real-CUGAN is omitted from this diagnostic build.\n"
    )
    (LICENSES_DIR / "README.txt").write_text(
        "MangaCrisp third-party notices for the Linux x86_64 build.\n\n"
        "Keep every file in this directory with redistributed builds.\n"
        f"{archive_summary}{engine_summary}",
        encoding="utf-8",
    )
    return LICENSES_DIR


def write_icons(destination: Path) -> None:
    with Image.open(APP_ICON_SOURCE) as source:
        image = source.convert("RGBA")
        for size in ICON_SIZES:
            target = destination / f"{size}x{size}" / f"{APP_ID}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            image.resize((size, size), Image.LANCZOS).save(target)


def copy_public_files(licenses_dir: Path, archive_tool_dir: Path | None, engine_dir: Path | None) -> None:
    shutil.copytree(licenses_dir, DIST_APP / "licenses")
    if archive_tool_dir is not None:
        shutil.copytree(archive_tool_dir, DIST_APP / "tools" / "7zip")
    if engine_dir is not None:
        shutil.copytree(engine_dir, DIST_APP / "_internal" / "engines" / "realcugan-ncnn-vulkan")
    share_dir = DIST_APP / "share"
    write_icons(share_dir / "icons")
    shutil.copy2(PACKAGING_DIR / f"{APP_ID}.desktop", share_dir / f"{APP_ID}.desktop")
    for script in ("install.sh", "uninstall.sh"):
        shutil.copy2(PACKAGING_DIR / script, DIST_APP / script)
        (DIST_APP / script).chmod(0o755)
    for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md", "INSTALL.linux.md", "INSTALL.linux.ja.md"):
        source = ROOT_DIR / filename
        if source.is_file():
            shutil.copy2(source, DIST_APP / filename)


def smoke_test(executable: Path) -> None:
    with TemporaryDirectory(prefix="mangacrisp-linux-build-") as temporary:
        home = Path(temporary)
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(home),
                "XDG_DATA_HOME": str(home / "data"),
                "XDG_CACHE_HOME": str(home / "cache"),
                "MANGACRISP_LANGUAGE": "en",
                "QT_QPA_PLATFORM": "offscreen",
            }
        )
        subprocess.run([str(executable), "--smoke-test"], cwd=DIST_APP, env=environment, check=True, timeout=60)


def create_archive() -> Path:
    target = archive_path()
    target.unlink(missing_ok=True)

    def normalize(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        return info

    with tarfile.open(target, "w:gz") as archive:
        archive.add(DIST_APP, arcname="MangaCrisp", filter=normalize)
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Linux x86_64 MangaCrisp one-folder application.")
    parser.add_argument("--skip-smoke-test", action="store_true")
    parser.add_argument("--without-archive-tool", action="store_true", help="omit the pinned 7-Zip backend")
    parser.add_argument("--without-engine", action="store_true", help="omit Real-CUGAN from a diagnostic build")
    parser.add_argument("--no-archive", action="store_true", help="do not create the .tar.gz release archive")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if platform.system() != "Linux":
        raise SystemExit("Linux builds must run on Linux.")
    if platform.machine().lower() not in {"x86_64", "amd64"}:
        raise SystemExit(f"Linux x86_64 is required, found: {platform.machine()}")

    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(DIST_APP, ignore_errors=True)
    archive_tool_dir = None if args.without_archive_tool else ensure_7zip(VENDOR_DIR)
    engine_dir = None if args.without_engine else ensure_realcugan(VENDOR_DIR)
    licenses_dir = prepare_license_files(archive_tool_dir, engine_dir)
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--noupx",
        "--name",
        "MangaCrisp",
        "--paths",
        str(ROOT_DIR / "src"),
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR / "pyinstaller"),
        "--specpath",
        str(BUILD_DIR),
        "--hidden-import",
        "mangacrisp_app.bookshelf",
        "--hidden-import",
        "mangacrisp_app.library",
        "--hidden-import",
        "mangacrisp_app.page_provider",
        "--hidden-import",
        "mangacrisp_app.platform.linux",
        "--hidden-import",
        "mangacrisp_app.platform.capture_linux",
        "--hidden-import",
        "jeepney.io.blocking",
        "--exclude-module",
        "numpy",
        "--exclude-module",
        "cv2",
        str(ENTRYPOINT),
    ]
    subprocess.run(command, cwd=ROOT_DIR, check=True)
    if not DIST_EXECUTABLE.is_file():
        raise SystemExit(f"build did not create {DIST_EXECUTABLE}")
    copy_public_files(licenses_dir, archive_tool_dir, engine_dir)
    if not args.skip_smoke_test:
        smoke_test(DIST_EXECUTABLE)
    print(f"built: {DIST_APP}")
    if not args.no_archive:
        print(f"archive: {create_archive()}")


if __name__ == "__main__":
    main()
