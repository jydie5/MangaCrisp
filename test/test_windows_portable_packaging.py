from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

SCRIPT_PATH = SCRIPTS_DIR / "package_windows_portable.py"
SPEC = importlib.util.spec_from_file_location(
    "package_windows_portable",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


def test_development_suffix_distinguishes_local_and_public_artifacts() -> None:
    assert (
        PACKAGE.development_suffix(
            release_ready=False,
            development_baseline=True,
            development_preview=False,
        )
        == "-baseline"
    )
    assert (
        PACKAGE.development_suffix(
            release_ready=False,
            development_baseline=False,
            development_preview=True,
        )
        == "-preview"
    )
    assert (
        PACKAGE.development_suffix(
            release_ready=True,
            development_baseline=False,
            development_preview=False,
        )
        == ""
    )

    with pytest.raises(SystemExit, match="release audit is incomplete"):
        PACKAGE.development_suffix(
            release_ready=False,
            development_baseline=False,
            development_preview=False,
        )


def test_preview_allows_only_documented_external_validation_blockers() -> None:
    PACKAGE.validate_preview_blockers(
        {
            "release_blockers": [
                "clean_windows_account has not passed",
                "gpu_intel has not passed",
                "gpu_amd has not passed",
            ]
        }
    )

    with pytest.raises(SystemExit, match="unexpected release blockers"):
        PACKAGE.validate_preview_blockers(
            {
                "release_blockers": [
                    "gpu_nvidia was not validated against the bundled engine"
                ]
            }
        )
