from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pefile

from mangacrisp_app.platform import subprocess_window_kwargs


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "dist" / "MangaCrisp"
APP_EXE = APP_DIR / "MangaCrisp.exe"
REPORT_PATH = ROOT_DIR / "dist" / "windows-distribution-audit.json"
REQUIRED_PUBLIC_FILES = {
    "INSTALL.windows.md",
    "INSTALL.windows.ja.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "licenses/README.txt",
    "licenses/MangaCrisp-MIT.txt",
}
REQUIRED_LICENSE_PREFIXES = {
    "Python-PyInstaller-",
    "Python-PySide6-",
    "Python-shiboken6-",
    "Python-Pillow-",
    "Python-py7zr-",
    "Python-rarfile-",
    "Python-3.",
    "Qt-PySide6-source-and-relinking.txt",
}
FORBIDDEN_COMPONENTS = {
    ".venv",
    "__pycache__",
    "sample",
    "test",
}
FORBIDDEN_EXECUTABLES = {
    "python.exe",
    "pythonw.exe",
    "uv.exe",
    "uvx.exe",
}
TEXT_SUFFIXES = {".cfg", ".html", ".ini", ".json", ".md", ".txt", ".xml"}


def relative_files() -> list[Path]:
    return sorted(
        (path.relative_to(APP_DIR) for path in APP_DIR.rglob("*") if path.is_file()),
        key=lambda path: str(path).lower(),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def smoke_test() -> dict[str, object]:
    started = time.perf_counter()
    with TemporaryDirectory(prefix="mangacrisp-windows-audit-") as temporary:
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
        completed = subprocess.run(
            [str(APP_EXE), "--smoke-test"],
            cwd=APP_DIR,
            env=environment,
            check=False,
            timeout=30,
            **subprocess_window_kwargs(),
        )
    return {
        "returncode": completed.returncode,
        "elapsed_sec": round(time.perf_counter() - started, 3),
    }


def text_path_leaks(files: list[Path]) -> list[str]:
    needles = {
        str(ROOT_DIR).lower(),
        str(Path.home()).lower(),
    }
    leaks: list[str] = []
    for relative_path in files:
        if relative_path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        path = APP_DIR / relative_path
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        if any(needle and needle in content for needle in needles):
            leaks.append(str(relative_path))
    return leaks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the Windows x64 MangaCrisp one-folder distribution."
    )
    parser.add_argument(
        "--require-engine",
        action="store_true",
        help="fail unless the pinned Real-CUGAN executable and provenance are bundled",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not APP_EXE.is_file():
        raise SystemExit(f"missing Windows application: {APP_EXE}")

    files = relative_files()
    file_names = {str(path).replace("\\", "/") for path in files}
    license_names = {
        path.name
        for path in files
        if path.parts and path.parts[0].lower() == "licenses"
    }
    missing_public_files = sorted(REQUIRED_PUBLIC_FILES - file_names)
    missing_license_prefixes = sorted(
        prefix
        for prefix in REQUIRED_LICENSE_PREFIXES
        if not any(name.startswith(prefix) for name in license_names)
    )
    forbidden_paths = sorted(
        str(path)
        for path in files
        if FORBIDDEN_COMPONENTS.intersection(part.lower() for part in path.parts)
        or path.suffix.lower() in {".pyc", ".pdb"}
    )
    forbidden_executables = sorted(
        str(path) for path in files if path.name.lower() in FORBIDDEN_EXECUTABLES
    )
    engine_files = [
        path
        for path in files
        if path.name.lower() == "realcugan-ncnn-vulkan.exe"
    ]
    engine_bundled = bool(engine_files)
    engine_provenance = "realcugan-provenance.json" in license_names
    engine_license = "realcugan-ncnn-vulkan-MIT.txt" in license_names

    pe = pefile.PE(str(APP_EXE), fast_load=True)
    machine = pe.FILE_HEADER.Machine
    subsystem = pe.OPTIONAL_HEADER.Subsystem
    pe.close()
    smoke = smoke_test()
    path_leaks = text_path_leaks(files)

    failures: list[str] = []
    if machine != pefile.MACHINE_TYPE["IMAGE_FILE_MACHINE_AMD64"]:
        failures.append(f"MangaCrisp.exe is not AMD64: machine=0x{machine:04x}")
    if subsystem != pefile.SUBSYSTEM_TYPE["IMAGE_SUBSYSTEM_WINDOWS_GUI"]:
        failures.append(f"MangaCrisp.exe is not a GUI subsystem binary: {subsystem}")
    if missing_public_files:
        failures.append("public files are missing")
    if missing_license_prefixes:
        failures.append("runtime license notices are missing")
    if forbidden_paths:
        failures.append("forbidden development paths are present")
    if forbidden_executables:
        failures.append("end-user Python or uv executables are present")
    if path_leaks:
        failures.append("local absolute paths leaked into text files")
    if smoke["returncode"] != 0:
        failures.append("packaged application smoke test failed")
    if engine_bundled and not (engine_provenance and engine_license):
        failures.append("bundled engine is missing provenance or its license")
    if args.require_engine and not engine_bundled:
        failures.append("Real-CUGAN is required but not bundled")

    report = {
        "application": str(APP_DIR.relative_to(ROOT_DIR)),
        "executable": str(APP_EXE.relative_to(ROOT_DIR)),
        "executable_sha256": sha256_file(APP_EXE),
        "file_count": len(files),
        "size_bytes": sum((APP_DIR / path).stat().st_size for path in files),
        "machine": f"0x{machine:04x}",
        "amd64": machine == pefile.MACHINE_TYPE["IMAGE_FILE_MACHINE_AMD64"],
        "subsystem": subsystem,
        "gui_subsystem": subsystem
        == pefile.SUBSYSTEM_TYPE["IMAGE_SUBSYSTEM_WINDOWS_GUI"],
        "python_required_for_end_user": False,
        "smoke_test": smoke,
        "engine_bundled": engine_bundled,
        "engine_files": [str(path) for path in engine_files],
        "engine_provenance": engine_provenance,
        "engine_license": engine_license,
        "missing_public_files": missing_public_files,
        "missing_license_prefixes": missing_license_prefixes,
        "forbidden_paths": forbidden_paths,
        "forbidden_executables": forbidden_executables,
        "text_path_leaks": path_leaks,
        "failures": failures,
        "baseline_ready": not failures,
        "release_ready": not failures and engine_bundled,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"report: {REPORT_PATH}")
    print(
        f"baseline_ready={report['baseline_ready']} "
        f"release_ready={report['release_ready']} "
        f"amd64={report['amd64']} gui={report['gui_subsystem']} "
        f"engine_bundled={engine_bundled} files={len(files)}"
    )
    if failures:
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
