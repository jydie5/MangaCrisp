from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
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

WINDOWS_APP_SCRIPT_PATH = SCRIPTS_DIR / "build_windows_app.py"
WINDOWS_APP_SPEC = importlib.util.spec_from_file_location(
    "build_windows_app",
    WINDOWS_APP_SCRIPT_PATH,
)
assert WINDOWS_APP_SPEC is not None and WINDOWS_APP_SPEC.loader is not None
BUILD_WINDOWS_APP = importlib.util.module_from_spec(WINDOWS_APP_SPEC)
WINDOWS_APP_SPEC.loader.exec_module(BUILD_WINDOWS_APP)


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


def test_lld_metadata_normalization_is_deterministic() -> None:
    data = bytearray(96)
    data[12:16] = bytes.fromhex("01020304")
    data[28:32] = bytes.fromhex("05060708")
    data[44:48] = bytes.fromhex("090a0b0c")
    data[60:80] = b"RSDS" + b"random!!" + b"LLD PDB."

    BUILD_REALCUGAN.apply_lld_metadata_normalization(
        data,
        file_timestamp_offset=12,
        debug_timestamp_offsets=[28, 44],
        codeview_offset=60,
    )

    timestamp = BUILD_REALCUGAN.CANONICAL_PE_TIMESTAMP.to_bytes(4, "little")
    assert data[12:16] == timestamp
    assert data[28:32] == timestamp
    assert data[44:48] == timestamp
    assert data[64:72] == BUILD_REALCUGAN.CANONICAL_LLD_PDB_HASH
    assert data[72:80] == b"LLD PDB."


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


def test_windows_build_copies_pdfium_runtime_licenses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BUILD_WINDOWS_APP, "RUNTIME_DISTRIBUTIONS", ("pypdfium2",))
    BUILD_WINDOWS_APP.copy_distribution_licenses(tmp_path)

    pdfium_notices = list(tmp_path.glob("Python-pypdfium2-*"))
    assert pdfium_notices
    assert any(path.name.endswith("-Apache-2.0.txt") for path in pdfium_notices)
    assert any(path.name.endswith("-pdfium.txt") for path in pdfium_notices)


def test_windows_build_isolates_dll_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system_root = tmp_path / "Windows"
    python_root = tmp_path / "Python"
    executable = tmp_path / "venv" / "Scripts" / "python.exe"
    inherited = {
        "SystemRoot": str(system_root),
        "PATH": str(tmp_path / "unrelated-tools"),
        "PYTHONHOME": str(tmp_path / "another-python"),
        "PYTHONPATH": str(tmp_path / "other-modules"),
        "QT_PLUGIN_PATH": str(tmp_path / "other-qt"),
        "QT_QPA_PLATFORM_PLUGIN_PATH": str(tmp_path / "other-qt-platforms"),
        "PYTHONUTF8": "1",
    }
    monkeypatch.setattr(BUILD_WINDOWS_APP.os, "environ", inherited)
    monkeypatch.setattr(BUILD_WINDOWS_APP.sys, "executable", str(executable))
    monkeypatch.setattr(BUILD_WINDOWS_APP.sys, "base_prefix", str(python_root))

    environment = BUILD_WINDOWS_APP.pyinstaller_environment()

    assert environment["PATH"].split(os.pathsep) == [
        str(system_root / "System32"),
        str(system_root),
        str(executable.resolve().parent),
        str(python_root),
        str(python_root / "DLLs"),
    ]
    for key in (
        "PYTHONHOME",
        "PYTHONPATH",
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
    ):
        assert key not in environment
        assert key in inherited
    assert environment["PYTHONUTF8"] == "1"
    assert inherited["PATH"] == str(tmp_path / "unrelated-tools")


def test_windows_build_uses_default_system_root_and_deduplicates_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BUILD_WINDOWS_APP.os, "environ", {})
    monkeypatch.setattr(
        BUILD_WINDOWS_APP.sys, "executable", str(tmp_path / "python.exe")
    )
    monkeypatch.setattr(BUILD_WINDOWS_APP.sys, "base_prefix", str(tmp_path.resolve()))

    # Compare the joined value: the default Windows drive colon is not a PATH
    # separator, even when this Windows-specific helper is tested on Linux.
    assert BUILD_WINDOWS_APP.pyinstaller_environment()["PATH"] == os.pathsep.join(
        (
            str(Path(r"C:\Windows") / "System32"),
            str(Path(r"C:\Windows")),
            str(tmp_path.resolve()),
            str(tmp_path.resolve() / "DLLs"),
        )
    )


@pytest.mark.parametrize(
    "runtime",
    ["vcomp140.dll", "libwinpthread-1.dll", "unexpected-runtime.dll"],
)
def test_zig_engine_runtime_imports_reject_non_system_runtime(runtime: str) -> None:
    with pytest.raises(RuntimeError, match="runtime imports"):
        BUILD_REALCUGAN.validate_runtime_imports(
            ["kernel32.dll", "vulkan-1.dll", runtime]
        )
