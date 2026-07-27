from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fetch_realcugan_windows.py"
SPEC = importlib.util.spec_from_file_location("fetch_realcugan_windows", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
FETCH_REALCUGAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FETCH_REALCUGAN)

FILE_SHA256 = FETCH_REALCUGAN.FILE_SHA256
safe_extract = FETCH_REALCUGAN.safe_extract
write_provenance = FETCH_REALCUGAN.write_provenance


def test_realcugan_zip_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "blocked")

    output = tmp_path / "output"
    output.mkdir()
    with zipfile.ZipFile(archive_path) as archive:
        with pytest.raises(RuntimeError, match="unsafe ZIP member"):
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
