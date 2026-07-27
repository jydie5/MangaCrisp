from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path


RELEASE = "20220728"
ARCHIVE_NAME = f"realcugan-ncnn-vulkan-{RELEASE}-windows.zip"
ARCHIVE_URL = (
    "https://github.com/nihui/realcugan-ncnn-vulkan/releases/download/"
    f"{RELEASE}/{ARCHIVE_NAME}"
)
ARCHIVE_SHA256 = "c6e08d46c11704b1e3a1ada9ddd591cb5005f52f132136c8633ba25def400e01"
PACKAGE_ROOT = f"realcugan-ncnn-vulkan-{RELEASE}-windows"
FILE_SHA256 = {
    "realcugan-ncnn-vulkan.exe": (
        "af5a36b124c993c77d0e69e42f640cdc108060874ed060d34ceef66d52c77a9d"
    ),
    "vcomp140.dll": (
        "54fe6b087528b33c2969143d811eb62f1bd49071d37de9db0745fc079764d698"
    ),
}
REQUIRED_MODEL_DIRS = ("models-nose", "models-pro", "models-se")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url: str, destination: Path, expected_sha256: str) -> Path:
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)
    with urllib.request.urlopen(url) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
    actual = sha256_file(temporary)
    if actual != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA-256 mismatch for {destination.name}: "
            f"expected {expected_sha256}, got {actual}"
        )
    temporary.replace(destination)
    return destination


def verify_tool_directory(tool_dir: Path) -> bool:
    binary_files_match = all(
        (tool_dir / filename).is_file()
        and sha256_file(tool_dir / filename) == expected
        for filename, expected in FILE_SHA256.items()
    )
    models_present = all(
        (tool_dir / directory).is_dir()
        and any((tool_dir / directory).glob("*.bin"))
        and any((tool_dir / directory).glob("*.param"))
        for directory in REQUIRED_MODEL_DIRS
    )
    return (
        binary_files_match
        and models_present
        and (tool_dir / "LICENSE").is_file()
        and (tool_dir / "README.md").is_file()
    )


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for info in archive.infolist():
        target = (destination / info.filename).resolve()
        if target != root and root not in target.parents:
            raise RuntimeError(f"unsafe ZIP member: {info.filename}")
    archive.extractall(destination)


def ensure_realcugan(destination: Path) -> Path:
    tool_dir = destination / PACKAGE_ROOT
    if verify_tool_directory(tool_dir):
        return tool_dir

    archive_path = download_verified(
        ARCHIVE_URL,
        destination / ARCHIVE_NAME,
        ARCHIVE_SHA256,
    )
    extract_dir = destination / f".{PACKAGE_ROOT}-extract"
    shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        safe_extract(archive, extract_dir)

    source = extract_dir / PACKAGE_ROOT
    if not source.is_dir():
        raise RuntimeError(f"expected package root was not found: {PACKAGE_ROOT}")
    shutil.rmtree(tool_dir, ignore_errors=True)
    shutil.copytree(source, tool_dir)
    shutil.rmtree(extract_dir, ignore_errors=True)
    if not verify_tool_directory(tool_dir):
        raise RuntimeError("extracted Real-CUGAN files did not match pinned values")
    return tool_dir


def write_provenance(destination: Path, tool_dir: Path) -> Path:
    payload = {
        "component": "Real-CUGAN ncnn Vulkan",
        "purpose": "Windows AI image enhancement engine",
        "release": RELEASE,
        "architecture": "x64",
        "archive_url": ARCHIVE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "files": {
            filename: sha256_file(tool_dir / filename)
            for filename in (*FILE_SHA256, "LICENSE", "README.md")
        },
        "project_license": "MIT",
        "modified": False,
        "redistribution_approved": False,
        "redistribution_blocker": (
            "Document eligibility or an alternate compliant route for "
            "Microsoft vcomp140.dll before public distribution."
        ),
        "microsoft_guidance": [
            "https://learn.microsoft.com/en-us/cpp/windows/"
            "redistributing-visual-cpp-files?view=msvc-170",
            "https://learn.microsoft.com/en-us/cpp/windows/"
            "latest-supported-vc-redist?view=msvc-170",
        ],
    }
    path = destination / "realcugan-provenance.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    resolved = ensure_realcugan(root / "build" / "vendor")
    provenance = write_provenance(resolved, resolved)
    print(f"Real-CUGAN: {resolved}")
    print(f"provenance: {provenance}")
    print("redistribution_approved=false (development validation only)")
