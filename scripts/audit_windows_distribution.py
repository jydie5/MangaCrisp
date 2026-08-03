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
from windows_release_validation import audit_release_validation

from mangacrisp_app.platform import subprocess_window_kwargs

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "dist" / "MangaCrisp"
APP_EXE = APP_DIR / "MangaCrisp.exe"
REPORT_PATH = ROOT_DIR / "dist" / "windows-distribution-audit.json"
ENGINE_DIR = APP_DIR / "_internal" / "engines" / "realcugan-ncnn-vulkan"
ENGINE_EXE = ENGINE_DIR / "realcugan-ncnn-vulkan.exe"
ENGINE_PROVENANCE = ENGINE_DIR / "realcugan-provenance.json"
RELEASE_VALIDATION_PATH = ROOT_DIR / "packaging" / "windows" / "release-validation.json"
REQUIRED_MODEL_DIRS = ("models-se", "models-pro", "models-nose")
FORBIDDEN_ENGINE_IMPORT_PREFIXES = (
    "libgcc",
    "libgomp",
    "libstdc++",
    "libwinpthread",
    "msvcp",
    "vcomp",
    "vcruntime",
)
ALLOWED_ENGINE_IMPORTS = {
    "kernel32.dll",
    "ole32.dll",
    "oleaut32.dll",
    "vulkan-1.dll",
}

ARCHIVE_TOOL_DIR = APP_DIR / "tools" / "7zip"
ARCHIVE_TOOL_HASHES = {
    "7z.exe": "83967f1b02b43c4efeda302795722c809e0e81b8307de73558d10484d5676a7d",
    "7z.dll": "69fd4df057985c40e510e2fac182881c7f85e90aa13ec703f763a8fdb2ce61f8",
}


REQUIRED_PUBLIC_FILES = {
    "INSTALL.windows.md",
    "INSTALL.windows.ja.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "licenses/README.txt",
    "licenses/MangaCrisp-MIT.txt",
    "licenses/7-Zip-License.txt",
    "licenses/7-Zip-readme.txt",
    "licenses/7zip-provenance.json",
}
REQUIRED_RUNTIME_FILES = {
    "_internal/pypdfium2_raw/pdfium.dll",
}
REQUIRED_LICENSE_PREFIXES = {
    "Python-PyInstaller-",
    "Python-PySide6-",
    "Python-shiboken6-",
    "Python-Pillow-",
    "Python-py7zr-",
    "Python-rarfile-",
    "Python-pypdfium2-",
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


def archive_backend_audit() -> dict[str, object]:
    files = {name: ARCHIVE_TOOL_DIR / name for name in ARCHIVE_TOOL_HASHES}
    bundled = all(path.is_file() for path in files.values())
    hashes = {
        name: sha256_file(path) if path.is_file() else None
        for name, path in files.items()
    }
    hash_verified = bundled and all(
        hashes[name] == expected for name, expected in ARCHIVE_TOOL_HASHES.items()
    )
    probe_returncode: int | None = None
    rar_supported = False
    if bundled:
        completed = subprocess.run(
            [str(files["7z.exe"]), "i"],
            cwd=ARCHIVE_TOOL_DIR,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
            **subprocess_window_kwargs(),
        )
        probe_returncode = completed.returncode
        formats = completed.stdout.lower()
        rar_supported = (
            completed.returncode == 0
            and " rar " in f" {formats} "
            and " rar5 " in f" {formats} "
        )
    return {
        "bundled": bundled,
        "hashes": hashes,
        "hash_verified": hash_verified,
        "probe_returncode": probe_returncode,
        "rar_and_rar5_supported": rar_supported,
    }


def executable_imports(path: Path) -> list[str]:
    pe = pefile.PE(str(path), fast_load=True)
    try:
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]]
        )
        return sorted(
            entry.dll.decode("ascii", errors="replace")
            for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])
        )
    finally:
        pe.close()


def engine_distribution_audit() -> dict[str, object]:
    bundled = ENGINE_EXE.is_file()
    provenance_present = ENGINE_PROVENANCE.is_file()
    errors: list[str] = []
    payload: dict[str, object] = {}
    if provenance_present:
        try:
            loaded = json.loads(ENGINE_PROVENANCE.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise TypeError("provenance root must be an object")
            payload = loaded
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            errors.append(f"invalid engine provenance: {exc}")
    elif bundled:
        errors.append("engine provenance is missing")
    elif ENGINE_DIR.exists():
        errors.append("engine directory exists without the executable")

    engine_hash = sha256_file(ENGINE_EXE) if bundled else None
    engine_record = payload.get("engine", {})
    if not isinstance(engine_record, dict):
        engine_record = {}
    provenance_hash = engine_record.get("sha256")
    hash_verified = bool(engine_hash and engine_hash == provenance_hash)
    if bundled and not hash_verified:
        errors.append("engine hash does not match provenance")

    machine: int | None = None
    if bundled:
        pe = pefile.PE(str(ENGINE_EXE), fast_load=True)
        machine = pe.FILE_HEADER.Machine
        pe.close()
        if machine != pefile.MACHINE_TYPE["IMAGE_FILE_MACHINE_AMD64"]:
            errors.append(f"engine is not AMD64: machine=0x{machine:04x}")

    imports = executable_imports(ENGINE_EXE) if bundled else []
    normalized_imports = {name.lower() for name in imports}
    expected_imports = {
        str(name).lower()
        for name in engine_record.get("imports", [])
        if isinstance(name, str)
    }
    imports_match = bool(bundled and normalized_imports == expected_imports)
    if bundled and not imports_match:
        errors.append("engine imports do not match provenance")
    forbidden_imports = sorted(
        name
        for name in normalized_imports
        if name.startswith(FORBIDDEN_ENGINE_IMPORT_PREFIXES)
    )
    unexpected_imports = sorted(
        name
        for name in normalized_imports
        if name not in ALLOWED_ENGINE_IMPORTS
        and not name.startswith(("api-ms-win-", "ext-ms-win-"))
    )
    if forbidden_imports:
        errors.append("engine imports a forbidden redistributed runtime")
    if unexpected_imports:
        errors.append("engine imports an unexpected runtime library")

    bundled_dlls = (
        sorted(
            str(path.relative_to(ENGINE_DIR)).replace("\\", "/")
            for path in ENGINE_DIR.rglob("*.dll")
            if path.is_file()
        )
        if ENGINE_DIR.exists()
        else []
    )
    if bundled_dlls:
        errors.append("engine directory contains bundled DLLs")
    unexpected_executables = (
        sorted(
            str(path.relative_to(ENGINE_DIR)).replace("\\", "/")
            for path in ENGINE_DIR.rglob("*.exe")
            if path.is_file() and path != ENGINE_EXE
        )
        if ENGINE_DIR.exists()
        else []
    )
    if unexpected_executables:
        errors.append("engine directory contains unexpected executables")

    models_record = payload.get("models", {})
    if not isinstance(models_record, dict):
        models_record = {}
    model_hashes = models_record.get("files", {})
    if not isinstance(model_hashes, dict):
        model_hashes = {}
    model_errors: list[str] = []
    for relative_name, expected_hash in model_hashes.items():
        model_path = ENGINE_DIR / str(relative_name)
        if not model_path.is_file():
            model_errors.append(f"missing {relative_name}")
        elif sha256_file(model_path) != expected_hash:
            model_errors.append(f"hash mismatch {relative_name}")
    manifest_model_names = {
        str(relative_name).replace("\\", "/") for relative_name in model_hashes
    }
    actual_model_names = {
        str(path.relative_to(ENGINE_DIR)).replace("\\", "/")
        for directory in REQUIRED_MODEL_DIRS
        for path in (ENGINE_DIR / directory).rglob("*")
        if path.is_file()
    }
    for relative_name in sorted(actual_model_names - manifest_model_names):
        model_errors.append(f"unrecorded {relative_name}")
    for directory in REQUIRED_MODEL_DIRS:
        model_dir = ENGINE_DIR / directory
        if not any(model_dir.glob("*.bin")) or not any(model_dir.glob("*.param")):
            model_errors.append(f"incomplete {directory}")
    if not model_hashes:
        model_errors.append("model hash manifest is empty")
    if model_errors:
        errors.append("engine model verification failed")

    license_hashes = payload.get("licenses", {})
    if not isinstance(license_hashes, dict):
        license_hashes = {}
    license_errors: list[str] = []
    for filename, expected_hash in license_hashes.items():
        engine_license = ENGINE_DIR / "licenses" / str(filename)
        public_license = APP_DIR / "licenses" / str(filename)
        if not engine_license.is_file() or sha256_file(engine_license) != expected_hash:
            license_errors.append(f"invalid engine notice {filename}")
        if not public_license.is_file() or sha256_file(public_license) != expected_hash:
            license_errors.append(f"invalid public notice {filename}")
    actual_license_names = (
        {path.name for path in (ENGINE_DIR / "licenses").iterdir() if path.is_file()}
        if (ENGINE_DIR / "licenses").is_dir()
        else set()
    )
    for filename in sorted(actual_license_names - set(license_hashes)):
        license_errors.append(f"unrecorded engine notice {filename}")
    if not license_hashes:
        license_errors.append("license hash manifest is empty")
    if license_errors:
        errors.append("engine license verification failed")

    public_provenance = APP_DIR / "licenses" / ENGINE_PROVENANCE.name
    public_provenance_verified = (
        provenance_present
        and public_provenance.is_file()
        and sha256_file(public_provenance) == sha256_file(ENGINE_PROVENANCE)
    )
    if bundled and not public_provenance_verified:
        errors.append("public engine provenance copy is missing or modified")

    approved = payload.get("redistribution_approved") is True
    return {
        "bundled": bundled,
        "directory": str(ENGINE_DIR.relative_to(APP_DIR)),
        "sha256": engine_hash,
        "provenance_present": provenance_present,
        "provenance_hash": provenance_hash,
        "hash_verified": hash_verified,
        "machine": f"0x{machine:04x}" if machine is not None else None,
        "amd64": machine == pefile.MACHINE_TYPE["IMAGE_FILE_MACHINE_AMD64"],
        "imports": imports,
        "imports_match_provenance": imports_match,
        "forbidden_imports": forbidden_imports,
        "unexpected_imports": unexpected_imports,
        "bundled_dlls": bundled_dlls,
        "model_errors": model_errors,
        "license_errors": license_errors,
        "unexpected_executables": unexpected_executables,
        "public_provenance_verified": public_provenance_verified,
        "redistribution_approved": approved,
        "errors": errors,
        "valid": bundled and not errors,
    }


def release_validation_audit(
    engine_hash: str | None,
    executable_hash: str | None,
) -> dict[str, object]:
    try:
        validation_path = str(RELEASE_VALIDATION_PATH.relative_to(ROOT_DIR))
    except ValueError:
        validation_path = RELEASE_VALIDATION_PATH.name
    result = audit_release_validation(
        RELEASE_VALIDATION_PATH,
        ROOT_DIR,
        engine_hash,
        executable_hash,
    )
    return {"path": validation_path, **result}


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
    missing_runtime_files = sorted(REQUIRED_RUNTIME_FILES - file_names)
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
    engine = engine_distribution_audit()
    engine_hash = engine["sha256"] if isinstance(engine["sha256"], str) else None
    executable_hash = sha256_file(APP_EXE)
    release_validation = release_validation_audit(
        engine_hash,
        executable_hash,
    )

    pe = pefile.PE(str(APP_EXE), fast_load=True)
    machine = pe.FILE_HEADER.Machine
    subsystem = pe.OPTIONAL_HEADER.Subsystem
    pe.close()
    smoke = smoke_test()
    path_leaks = text_path_leaks(files)
    archive_backend = archive_backend_audit()

    failures: list[str] = []
    if machine != pefile.MACHINE_TYPE["IMAGE_FILE_MACHINE_AMD64"]:
        failures.append(f"MangaCrisp.exe is not AMD64: machine=0x{machine:04x}")
    if subsystem != pefile.SUBSYSTEM_TYPE["IMAGE_SUBSYSTEM_WINDOWS_GUI"]:
        failures.append(f"MangaCrisp.exe is not a GUI subsystem binary: {subsystem}")
    if missing_public_files:
        failures.append("public files are missing")
    if missing_runtime_files:
        failures.append("required runtime files are missing")
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
    if not archive_backend["bundled"]:
        failures.append("the pinned 7-Zip archive backend is not bundled")
    elif not archive_backend["hash_verified"]:
        failures.append("the bundled 7-Zip files do not match pinned hashes")
    elif not archive_backend["rar_and_rar5_supported"]:
        failures.append(
            "the bundled 7-Zip backend does not report RAR and RAR5 support"
        )
    if engine["bundled"] and not engine["valid"]:
        failures.extend(f"engine: {error}" for error in engine["errors"])
    if engine["bundled"] and not engine["redistribution_approved"]:
        failures.append("bundled engine is not approved by its provenance")
    if args.require_engine and not engine["bundled"]:
        failures.append("Real-CUGAN is required but not bundled")

    release_blockers: list[str] = []
    if not engine["bundled"]:
        release_blockers.append("Real-CUGAN is not bundled")
    elif not engine["valid"]:
        release_blockers.append("Real-CUGAN distribution validation failed")
    elif not engine["redistribution_approved"]:
        release_blockers.append("Real-CUGAN redistribution is not approved")
    release_blockers.extend(release_validation["errors"])

    report = {
        "application": str(APP_DIR.relative_to(ROOT_DIR)),
        "executable": str(APP_EXE.relative_to(ROOT_DIR)),
        "executable_sha256": executable_hash,
        "file_count": len(files),
        "size_bytes": sum((APP_DIR / path).stat().st_size for path in files),
        "machine": f"0x{machine:04x}",
        "amd64": machine == pefile.MACHINE_TYPE["IMAGE_FILE_MACHINE_AMD64"],
        "subsystem": subsystem,
        "gui_subsystem": subsystem
        == pefile.SUBSYSTEM_TYPE["IMAGE_SUBSYSTEM_WINDOWS_GUI"],
        "python_required_for_end_user": False,
        "smoke_test": smoke,
        "engine_bundled": engine["bundled"],
        "archive_backend": archive_backend,
        "engine": engine,
        "release_validation": release_validation,
        "missing_public_files": missing_public_files,
        "missing_runtime_files": missing_runtime_files,
        "missing_license_prefixes": missing_license_prefixes,
        "forbidden_paths": forbidden_paths,
        "forbidden_executables": forbidden_executables,
        "text_path_leaks": path_leaks,
        "failures": failures,
        "release_blockers": release_blockers,
        "baseline_ready": not failures,
        "release_ready": not failures and not release_blockers,
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
        f"archive_backend={archive_backend['bundled']} "
        f"engine_bundled={engine['bundled']} files={len(files)}"
    )
    for blocker in release_blockers:
        print(f"- release blocker: {blocker}")
    if failures:
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
