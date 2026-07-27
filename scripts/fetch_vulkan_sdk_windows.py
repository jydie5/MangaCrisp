from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
VERSION = "1.4.350.0"
INSTALLER_NAME = f"vulkansdk-windows-X64-{VERSION}.exe"
INSTALLER_URL = (
    f"https://sdk.lunarg.com/sdk/download/{VERSION}/windows/{INSTALLER_NAME}"
)
INSTALLER_SHA256 = "855b27ba05d2d8119c5114c5d4ff870ca38f2c632b11e1bb9923b9b7e6ecfe7b"
PACKAGE_ROOT = f"VulkanSDK-{VERSION}"
REQUIRED_FILES = (
    Path("Include/vulkan/vulkan.h"),
    Path("Lib/vulkan-1.lib"),
    Path("Bin/glslc.exe"),
    Path("Licenses/LICENSE.txt"),
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


def verify_sdk(sdk_root: Path) -> bool:
    return all((sdk_root / relative).is_file() for relative in REQUIRED_FILES)


def write_provenance(sdk_root: Path, installer: Path) -> Path:
    payload = {
        "schema_version": 1,
        "component": "LunarG Vulkan SDK",
        "version": VERSION,
        "architecture": "x64",
        "purpose": "build-time headers, import library, and shader tools",
        "installer_url": INSTALLER_URL,
        "installer_sha256": sha256_file(installer),
        "install_mode": "copy_only",
        "copied_to_mangacrisp_distribution": False,
        "runtime_note": (
            "The Vulkan loader is supplied by Windows GPU drivers; MangaCrisp "
            "does not redistribute the SDK or its loader."
        ),
        "license_registry": "https://vulkan.lunarg.com/doc/sdk/latest/windows/release_notes.html",
    }
    path = sdk_root / "vulkan-sdk-provenance.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def ensure_vulkan_sdk(
    destination: Path,
    *,
    accept_licenses: bool = False,
) -> Path:
    destination = destination.resolve()
    installer = destination / INSTALLER_NAME
    sdk_root = destination / PACKAGE_ROOT
    if verify_sdk(sdk_root):
        if not installer.is_file() or sha256_file(installer) != INSTALLER_SHA256:
            raise RuntimeError(
                "The Vulkan SDK files exist but the pinned installer is unavailable "
                "for provenance verification. Re-run with --accept-licenses."
            )
        write_provenance(sdk_root, installer)
        return sdk_root
    if not accept_licenses:
        raise RuntimeError(
            "The pinned Vulkan SDK is not installed in the project cache. "
            "Run: uv run python scripts/fetch_vulkan_sdk_windows.py "
            "--accept-licenses"
        )

    installer = download_verified(INSTALLER_URL, installer, INSTALLER_SHA256)
    sdk_root.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(installer),
            "--root",
            str(sdk_root),
            "--accept-licenses",
            "--default-answer",
            "--confirm-command",
            "install",
            "copy_only=1",
        ],
        check=True,
        timeout=20 * 60,
    )
    if not verify_sdk(sdk_root):
        missing = [
            str(relative)
            for relative in REQUIRED_FILES
            if not (sdk_root / relative).is_file()
        ]
        raise RuntimeError(f"Vulkan SDK copy-only install is incomplete: {missing}")
    write_provenance(sdk_root, installer)
    return sdk_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch the pinned build-only Vulkan SDK in copy-only mode."
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=ROOT_DIR / "build" / "vendor",
    )
    parser.add_argument(
        "--accept-licenses",
        action="store_true",
        help="accept the upstream SDK licenses and perform a copy-only install",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    resolved = ensure_vulkan_sdk(
        args.destination,
        accept_licenses=args.accept_licenses,
    )
    print(f"Vulkan SDK: {resolved}")
    print(f"provenance: {resolved / 'vulkan-sdk-provenance.json'}")
