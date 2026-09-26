from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
RELEASE = "20220728"
PACKAGE_ROOT = f"realcugan-ncnn-vulkan-{RELEASE}-ubuntu"
ARCHIVE_NAME = f"{PACKAGE_ROOT}.zip"
ARCHIVE_URL = (
    "https://github.com/nihui/realcugan-ncnn-vulkan/releases/download/"
    f"{RELEASE}/{ARCHIVE_NAME}"
)
ARCHIVE_SHA256 = "d745174bd04c0232c89d935b74799311008fda06bea4195f61be5f0f3cc087cb"
EXECUTABLE_NAME = "realcugan-ncnn-vulkan"
EXECUTABLE_SHA256 = "89cb341d9ffbdcdc7f63bdc75d9cb0bae82eabe6597054e2a812331b2831fcc2"
REQUIRED_MODEL_DIRS = ("models-nose", "models-pro", "models-se")
# The official Ubuntu binary links only glibc, libstdc++, libgomp and the
# system Vulkan loader; none of those are bundled.
SYSTEM_LIBRARIES = ("libvulkan.so.1", "libgomp.so.1", "libstdc++.so.6")
DEFAULT_DESTINATION = ROOT_DIR / "test" / "engines"

LICENSE_SOURCES = (
    (
        "Real-CUGAN-models-MIT.txt",
        "https://raw.githubusercontent.com/bilibili/ailab/680c4a26444f0ff2c7c6bae3b0712f3b478c8184/Real-CUGAN/LICENSE",
        "8cad8cfdf94baaf23519061af913770e52476ddec2a311e9510582e7bed13cba",
    ),
    (
        "ncnn-LICENSE.txt",
        "https://raw.githubusercontent.com/Tencent/ncnn/066614351391d309c96ae1e00c6fb1bd873b4949/LICENSE.txt",
        "6495f972a09ad7f64ccd953e79adba91a93d862edc7135e6d95210bbf4002a01",
    ),
    (
        "libwebp-COPYING.txt",
        "https://raw.githubusercontent.com/webmproject/libwebp/b9d2f9cd3bec5b0970edeb11ea03c0a4ea06e332/COPYING",
        "5aec868f669e384a22372a4e8a1a6cd7d44c64cd451f960ca69cc170d1e13acf",
    ),
    (
        "libwebp-PATENTS.txt",
        "https://raw.githubusercontent.com/webmproject/libwebp/b9d2f9cd3bec5b0970edeb11ea03c0a4ea06e332/PATENTS",
        "cc3273e0694ea5896145e0677699b53471b03ea43021ddc50e7923fbb9f5023c",
    ),
)


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
    executable = tool_dir / EXECUTABLE_NAME
    models_present = all(
        (tool_dir / directory).is_dir()
        and any((tool_dir / directory).glob("*.bin"))
        and any((tool_dir / directory).glob("*.param"))
        for directory in REQUIRED_MODEL_DIRS
    )
    return (
        executable.is_file()
        and sha256_file(executable) == EXECUTABLE_SHA256
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


def ensure_realcugan(destination: Path, cache_dir: Path | None = None) -> Path:
    tool_dir = destination / PACKAGE_ROOT
    if verify_tool_directory(tool_dir):
        return tool_dir

    archive_path = download_verified(
        ARCHIVE_URL,
        (cache_dir or destination) / ARCHIVE_NAME,
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
    executable = tool_dir / EXECUTABLE_NAME
    # ZIP extraction drops the POSIX executable bit.
    executable.chmod(executable.stat().st_mode | 0o755)
    if not verify_tool_directory(tool_dir):
        raise RuntimeError("extracted Real-CUGAN files did not match pinned values")
    return tool_dir


def fetch_license_files(destination: Path) -> list[Path]:
    return [
        download_verified(url, destination / filename, expected_sha256)
        for filename, url, expected_sha256 in LICENSE_SOURCES
    ]


def write_provenance(destination: Path, tool_dir: Path) -> Path:
    payload = {
        "component": "Real-CUGAN ncnn Vulkan",
        "purpose": "Linux AI image enhancement engine",
        "release": RELEASE,
        "architecture": "x86_64",
        "archive_url": ARCHIVE_URL,
        "archive_sha256": ARCHIVE_SHA256,
        "files": {
            filename: sha256_file(tool_dir / filename)
            for filename in (EXECUTABLE_NAME, "LICENSE", "README.md")
        },
        "system_libraries": list(SYSTEM_LIBRARIES),
        "project_license": "MIT",
        "modified": False,
        "upstream": "https://github.com/nihui/realcugan-ncnn-vulkan",
        "model_source": "https://github.com/bilibili/ailab/tree/main/Real-CUGAN",
    }
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "realcugan-provenance.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch the pinned official Real-CUGAN Ubuntu package.")
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--licenses", type=Path)
    args = parser.parse_args()
    tool_dir = ensure_realcugan(args.destination, args.cache_dir)
    print(tool_dir)
    if args.licenses is not None:
        fetch_license_files(args.licenses)
        write_provenance(args.licenses, tool_dir)


if __name__ == "__main__":
    main()
