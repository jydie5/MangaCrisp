from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from fetch_7zip_windows import ensure_7zip, write_provenance


ROOT_DIR = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT_DIR / "src" / "mangacrisp_app" / "main.py"
APP_ICON_SOURCE = ROOT_DIR / "assets" / "mangacrisp-app-icon.png"
BUILD_DIR = ROOT_DIR / "build" / "windows"
APP_ICON = BUILD_DIR / "MangaCrisp.ico"
LICENSES_DIR = BUILD_DIR / "licenses"
DIST_APP = ROOT_DIR / "dist" / "MangaCrisp"
DIST_EXE = DIST_APP / "MangaCrisp.exe"
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
)


def build_app_icon() -> Path:
    if not APP_ICON_SOURCE.is_file():
        raise RuntimeError(f"app icon source was not found: {APP_ICON_SOURCE}")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(APP_ICON_SOURCE) as image:
        image.save(
            APP_ICON,
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    return APP_ICON


def copy_distribution_licenses(destination: Path) -> int:
    copied = 0
    for package_name in RUNTIME_DISTRIBUTIONS:
        distribution = importlib.metadata.distribution(package_name)
        sources = []
        for relative_path in distribution.files or []:
            name = Path(relative_path).name.lower()
            if not any(term in name for term in ("license", "copying", "notice")):
                continue
            source = Path(distribution.locate_file(relative_path))
            if source.is_file():
                sources.append(source)
        if not sources:
            raise RuntimeError(f"no license file found for runtime dependency: {package_name}")
        for index, source in enumerate(sources, start=1):
            suffix = "" if len(sources) == 1 else f"-{index}"
            filename = (
                f"Python-{package_name}-{distribution.version}{suffix}-{source.name}"
            )
            shutil.copy2(source, destination / filename)
            copied += 1
    return copied


def copy_python_license(destination: Path) -> Path:
    candidates = (
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
        Path(sys.base_prefix) / "Doc" / "license.rst",
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
        "MangaCrisp/_internal/PySide6/Qt/\n\n"
        "Compatible Qt/PySide6 DLLs may be replaced for relinking. If a future "
        "release is code-signed, replacing DLLs invalidates that signature.\n",
        encoding="utf-8",
    )


def prepare_license_files(archive_tool_dir: Path | None) -> Path:
    shutil.rmtree(LICENSES_DIR, ignore_errors=True)
    LICENSES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT_DIR / "LICENSE", LICENSES_DIR / "MangaCrisp-MIT.txt")
    shutil.copy2(
        ROOT_DIR / "THIRD_PARTY_NOTICES.md",
        LICENSES_DIR / "THIRD_PARTY_NOTICES.md",
    )
    copy_distribution_licenses(LICENSES_DIR)
    copy_python_license(LICENSES_DIR)
    write_qt_source_notice(LICENSES_DIR)
    if archive_tool_dir is not None:
        shutil.copy2(
            archive_tool_dir / "License.txt",
            LICENSES_DIR / "7-Zip-License.txt",
        )
        shutil.copy2(
            archive_tool_dir / "readme.txt",
            LICENSES_DIR / "7-Zip-readme.txt",
        )
        write_provenance(LICENSES_DIR, archive_tool_dir)
    archive_summary = (
        "The pinned 7-Zip command-line backend is bundled for RAR/CBR fallback extraction. "
        if archive_tool_dir is not None
        else "The 7-Zip archive backend is omitted from this diagnostic build. "
    )

    (LICENSES_DIR / "README.txt").write_text(
        "MangaCrisp third-party notices for the Windows one-folder build.\n\n"
        "Keep every file in this directory with redistributed builds.\n"
        f"{archive_summary}"
        "This development build does not bundle Real-CUGAN. Original-image "
        "reading remains available while the Microsoft runtime redistribution "
        "route is reviewed.\n",
        encoding="utf-8",
    )
    return LICENSES_DIR


def copy_public_files(
    licenses_dir: Path,
    archive_tool_dir: Path | None,
) -> None:
    shutil.copytree(licenses_dir, DIST_APP / "licenses")
    if archive_tool_dir is not None:
        shutil.copytree(archive_tool_dir, DIST_APP / "tools" / "7zip")
    for filename in (
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "INSTALL.windows.md",
        "INSTALL.windows.ja.md",
    ):
        source = ROOT_DIR / filename
        if source.is_file():
            shutil.copy2(source, DIST_APP / filename)


def smoke_test(executable: Path) -> None:
    with TemporaryDirectory(prefix="mangacrisp-windows-build-") as temporary:
        temporary_path = Path(temporary)
        environment = os.environ.copy()
        environment.update(
            {
                "APPDATA": str(temporary_path / "AppData" / "Roaming"),
                "LOCALAPPDATA": str(temporary_path / "AppData" / "Local"),
                "MANGACRISP_LANGUAGE": "en",
                "QT_QPA_PLATFORM": "offscreen",
                "USERPROFILE": str(temporary_path),
            }
        )
        subprocess.run(
            [str(executable), "--smoke-test"],
            cwd=DIST_APP,
            env=environment,
            check=True,
            timeout=30,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Windows x64 MangaCrisp one-folder application."
    )
    parser.add_argument(
        "--skip-smoke-test",
        action="store_true",
        help="build without launching the isolated packaged-app smoke test",
    )
    parser.add_argument(
        "--without-archive-tool",
        action="store_true",
        help="omit the pinned 7-Zip RAR/CBR backend (audit will reject the baseline)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if platform.system() != "Windows":
        raise SystemExit("Windows one-folder builds must run on Windows.")
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit(f"Windows x64 is required, found: {platform.machine()}")
    if not ENTRYPOINT.is_file():
        raise SystemExit(f"missing entrypoint: {ENTRYPOINT}")

    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    shutil.rmtree(DIST_APP, ignore_errors=True)
    app_icon = build_app_icon()
    archive_tool_dir = (
        None
        if args.without_archive_tool
        else ensure_7zip(ROOT_DIR / "build" / "vendor")
    )
    licenses_dir = prepare_license_files(archive_tool_dir)
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
        "--icon",
        str(app_icon),
        "--paths",
        str(ROOT_DIR / "src"),
        "--distpath",
        str(ROOT_DIR / "dist"),
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
        "mangacrisp_app.platform.windows",
        "--exclude-module",
        "numpy",
        "--exclude-module",
        "cv2",
        str(ENTRYPOINT),
    ]
    subprocess.run(command, cwd=ROOT_DIR, check=True)
    if not DIST_EXE.is_file():
        raise SystemExit(f"build did not create {DIST_EXE}")
    copy_public_files(licenses_dir, archive_tool_dir)
    if not args.skip_smoke_test:
        smoke_test(DIST_EXE)
    print(f"built: {DIST_APP}")
    print(f"executable: {DIST_EXE}")


if __name__ == "__main__":
    main()
