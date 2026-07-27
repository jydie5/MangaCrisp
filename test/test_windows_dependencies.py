from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

SCRIPT_PATH = SCRIPTS_DIR / "fetch_realcugan_windows.py"
SPEC = importlib.util.spec_from_file_location("fetch_realcugan_windows", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
FETCH_REALCUGAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FETCH_REALCUGAN)

FILE_SHA256 = FETCH_REALCUGAN.FILE_SHA256
safe_extract = FETCH_REALCUGAN.safe_extract
write_provenance = FETCH_REALCUGAN.write_provenance

BUILD_SCRIPT_PATH = SCRIPTS_DIR / "build_realcugan_windows.py"
BUILD_SPEC = importlib.util.spec_from_file_location(
    "build_realcugan_windows",
    BUILD_SCRIPT_PATH,
)
assert BUILD_SPEC is not None and BUILD_SPEC.loader is not None
BUILD_REALCUGAN = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(BUILD_REALCUGAN)

VULKAN_SCRIPT_PATH = SCRIPTS_DIR / "fetch_vulkan_sdk_windows.py"
VULKAN_SPEC = importlib.util.spec_from_file_location(
    "fetch_vulkan_sdk_windows",
    VULKAN_SCRIPT_PATH,
)
assert VULKAN_SPEC is not None and VULKAN_SPEC.loader is not None
FETCH_VULKAN = importlib.util.module_from_spec(VULKAN_SPEC)
VULKAN_SPEC.loader.exec_module(FETCH_VULKAN)


def test_realcugan_zip_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "blocked")

    output = tmp_path / "output"
    output.mkdir()
    with (
        zipfile.ZipFile(archive_path) as archive,
        pytest.raises(RuntimeError, match="unsafe ZIP member"),
    ):
        safe_extract(archive, output)

    assert not (tmp_path / "escape.txt").exists()


def test_realcugan_provenance_is_not_redistribution_approved(
    tmp_path: Path,
) -> None:
    tool_dir = tmp_path / "engine"
    tool_dir.mkdir()
    for filename in (*FILE_SHA256, "LICENSE", "README.md"):
        (tool_dir / filename).write_bytes(filename.encode("utf-8"))

    provenance_path = write_provenance(tmp_path, tool_dir)
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

    assert provenance["redistribution_approved"] is False
    assert "vcomp140.dll" in provenance["redistribution_blocker"]


def test_zig_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe-zig.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "blocked")

    output = tmp_path / "output"
    output.mkdir()
    with (
        zipfile.ZipFile(archive_path) as archive,
        pytest.raises(RuntimeError, match="unsafe ZIP member"),
    ):
        BUILD_REALCUGAN.safe_extract(archive, output)

    assert not (tmp_path / "escape.txt").exists()


def test_zig_engine_runtime_imports_accept_system_apis() -> None:
    BUILD_REALCUGAN.validate_runtime_imports(
        [
            "api-ms-win-crt-runtime-l1-1-0.dll",
            "kernel32.dll",
            "ole32.dll",
            "oleaut32.dll",
            "vulkan-1.dll",
        ]
    )


def test_vulkan_download_uses_cdn_compatible_headers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"verified Vulkan SDK installer"
    expected_sha256 = hashlib.sha256(payload).hexdigest()
    captured: dict[str, object] = {}

    def fake_urlopen(request: object) -> io.BytesIO:
        captured["request"] = request
        return io.BytesIO(payload)

    monkeypatch.setattr(FETCH_VULKAN.urllib.request, "urlopen", fake_urlopen)
    destination = tmp_path / "vulkan-sdk.exe"
    FETCH_VULKAN.download_verified(
        "https://sdk.lunarg.com/sdk/download/example.exe",
        destination,
        expected_sha256,
    )

    request = captured["request"]
    assert request.get_header("Accept") == "application/octet-stream"
    assert request.get_header("User-agent").startswith("MangaCrisp/")
    assert destination.read_bytes() == payload


@pytest.mark.parametrize(
    "runtime",
    ["vcomp140.dll", "libwinpthread-1.dll", "unexpected-runtime.dll"],
)
def test_zig_engine_runtime_imports_reject_non_system_runtime(runtime: str) -> None:
    with pytest.raises(RuntimeError, match="runtime imports"):
        BUILD_REALCUGAN.validate_runtime_imports(
            ["kernel32.dll", "vulkan-1.dll", runtime]
        )
