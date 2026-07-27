from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path


SEVEN_ZIP_VERSION = "26.02"
INSTALLER_NAME = "7z2602-x64.exe"
BOOTSTRAP_NAME = "7zr.exe"
INSTALLER_URL = (
    "https://github.com/ip7z/7zip/releases/download/"
    f"{SEVEN_ZIP_VERSION}/{INSTALLER_NAME}"
)
BOOTSTRAP_URL = (
    "https://github.com/ip7z/7zip/releases/download/"
    f"{SEVEN_ZIP_VERSION}/{BOOTSTRAP_NAME}"
)
INSTALLER_SHA256 = "6745fa76dc2ea031596d8678f6f6b99c3c1b435b4164a63485adbbc7b8d82ef0"
BOOTSTRAP_SHA256 = "56b8cc9f4971cef253644fafe54063ed7fdca551d4dee0f8c6baa81b855acd72"
TOOL_SHA256 = {
    "7z.exe": "83967f1b02b43c4efeda302795722c809e0e81b8307de73558d10484d5676a7d",
    "7z.dll": "69fd4df057985c40e510e2fac182881c7f85e90aa13ec703f763a8fdb2ce61f8",
}


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
    return all(
        (tool_dir / filename).is_file()
        and sha256_file(tool_dir / filename) == expected
        for filename, expected in TOOL_SHA256.items()
    ) and all((tool_dir / filename).is_file() for filename in ("License.txt", "readme.txt"))


def ensure_7zip(destination: Path) -> Path:
    tool_dir = destination / f"7zip-{SEVEN_ZIP_VERSION}-x64"
    if verify_tool_directory(tool_dir):
        return tool_dir

    cache_dir = destination / "cache"
    installer = download_verified(
        INSTALLER_URL,
        cache_dir / INSTALLER_NAME,
        INSTALLER_SHA256,
    )
    bootstrap = download_verified(
        BOOTSTRAP_URL,
        cache_dir / f"7zr-{SEVEN_ZIP_VERSION}.exe",
        BOOTSTRAP_SHA256,
    )
    extract_dir = destination / f".7zip-{SEVEN_ZIP_VERSION}-extract"
    shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True)
    subprocess.run(
        [str(bootstrap), "x", "-y", str(installer), f"-o{extract_dir}"],
        check=True,
    )
    shutil.rmtree(tool_dir, ignore_errors=True)
    tool_dir.mkdir(parents=True)
    for filename in ("7z.exe", "7z.dll", "License.txt", "readme.txt"):
        shutil.copy2(extract_dir / filename, tool_dir / filename)
    shutil.rmtree(extract_dir, ignore_errors=True)
    if not verify_tool_directory(tool_dir):
        raise RuntimeError("extracted 7-Zip files did not match pinned SHA-256 values")
    return tool_dir


def write_provenance(destination: Path, tool_dir: Path) -> Path:
    payload = {
        "component": "7-Zip",
        "purpose": "RAR/CBR fallback extraction",
        "version": SEVEN_ZIP_VERSION,
        "architecture": "x64",
        "installer_url": INSTALLER_URL,
        "installer_sha256": INSTALLER_SHA256,
        "bootstrap_url": BOOTSTRAP_URL,
        "bootstrap_sha256": BOOTSTRAP_SHA256,
        "files": {
            filename: sha256_file(tool_dir / filename)
            for filename in ("7z.exe", "7z.dll", "License.txt", "readme.txt")
        },
        "source": "https://www.7-zip.org/",
        "license": "GNU LGPL 2.1 or later with BSD components and unRAR restriction",
        "modified": False,
    }
    path = destination / "7zip-provenance.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    resolved = ensure_7zip(root / "build" / "vendor")
    print(f"7-Zip: {resolved}")
