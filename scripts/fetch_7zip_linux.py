from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SEVEN_ZIP_VERSION = "26.02"
ARCHIVE_NAME = "7z2602-linux-x64.tar.xz"
ARCHIVE_URL = f"https://github.com/ip7z/7zip/releases/download/{SEVEN_ZIP_VERSION}/{ARCHIVE_NAME}"
ARCHIVE_SHA256 = "41aaba7b1235304ab5aa0624530c67ae829496cd29e875925271efdccc28c03e"
# Only the dynamically linked console binary and its notices are bundled.
FILE_SHA256 = {
    "7zz": "1676a968815b92e865bc0ffeecee3fa284ba4402bf23dc2bec2412c4b502e922",
    "License.txt": "1790374e5352329cedb46ee3808930a88e9ca2f08b82b10fcf5cf605d2c301b1",
    "readme.txt": "c3ecf1b8f38631d6ef8a35048e80da77b31cf292a42b3e8793afd44bf4f001b0",
}
DEFAULT_DESTINATION = ROOT_DIR / "build" / "vendor"


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
    request = urllib.request.Request(url, headers={"User-Agent": "MangaCrisp-build"})
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
    actual = sha256_file(temporary)
    if actual != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA-256 mismatch for {destination.name}: expected {expected_sha256}, got {actual}"
        )
    temporary.replace(destination)
    return destination


def verify_tool_directory(tool_dir: Path) -> bool:
    return all(
        (tool_dir / filename).is_file() and sha256_file(tool_dir / filename) == expected
        for filename, expected in FILE_SHA256.items()
    )


def ensure_7zip(destination: Path = DEFAULT_DESTINATION) -> Path:
    tool_dir = destination / f"7zip-{SEVEN_ZIP_VERSION}-linux-x64"
    if verify_tool_directory(tool_dir):
        return tool_dir
    archive_path = download_verified(ARCHIVE_URL, destination / ARCHIVE_NAME, ARCHIVE_SHA256)
    shutil.rmtree(tool_dir, ignore_errors=True)
    tool_dir.mkdir(parents=True)
    with tarfile.open(archive_path, "r:xz") as archive:
        for filename in FILE_SHA256:
            member = archive.getmember(filename)
            if not member.isfile():
                raise RuntimeError(f"unexpected archive member type: {filename}")
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"cannot read archive member: {filename}")
            with source, (tool_dir / filename).open("wb") as output:
                shutil.copyfileobj(source, output)
    (tool_dir / "7zz").chmod(0o755)
    if not verify_tool_directory(tool_dir):
        raise RuntimeError("extracted 7-Zip files did not match pinned values")
    return tool_dir


def write_provenance(destination: Path, tool_dir: Path) -> Path:
    payload = {
        "component": "7-Zip",
        "purpose": "Linux RAR/CBR fallback extraction",
        "version": SEVEN_ZIP_VERSION,
        "architecture": "x86_64",
        "archive_url": ARCHIVE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "files": {filename: sha256_file(tool_dir / filename) for filename in FILE_SHA256},
        "license": "GNU LGPL with unRAR license restriction and BSD 3-clause parts; see License.txt",
        "modified": False,
        "upstream": "https://www.7-zip.org/",
    }
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "7zip-provenance.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch the pinned official 7-Zip Linux x64 console binary.")
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()
    print(ensure_7zip(args.destination))


if __name__ == "__main__":
    main()
