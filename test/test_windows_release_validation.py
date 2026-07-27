from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

VALIDATION_PATH = SCRIPTS_DIR / "windows_release_validation.py"
VALIDATION_SPEC = importlib.util.spec_from_file_location(
    "windows_release_validation_test",
    VALIDATION_PATH,
)
assert VALIDATION_SPEC is not None and VALIDATION_SPEC.loader is not None
VALIDATION = importlib.util.module_from_spec(VALIDATION_SPEC)
VALIDATION_SPEC.loader.exec_module(VALIDATION)

RECORD_PATH = SCRIPTS_DIR / "record_windows_release_validation.py"
RECORD_SPEC = importlib.util.spec_from_file_location(
    "record_windows_release_validation_test",
    RECORD_PATH,
)
assert RECORD_SPEC is not None and RECORD_SPEC.loader is not None
RECORD = importlib.util.module_from_spec(RECORD_SPEC)
RECORD_SPEC.loader.exec_module(RECORD)


def gpu_report(
    engine_hash: str = "a" * 64,
    device: str = "NVIDIA Test GPU",
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "validated_on": "2026-07-27",
        "gpu_inventory": [{"Name": device, "DriverVersion": "1.2.3"}],
        "engine": {
            "sha256": engine_hash,
            "provenance_hash": engine_hash,
            "provenance_hash_verified": True,
        },
        "input": {
            "archive": VALIDATION.EXPECTED_DEMO_ARCHIVE,
            "archive_sha256": VALIDATION.EXPECTED_DEMO_SHA256,
            "member": "01.jpg",
            "dimensions": [1200, 1660],
        },
        "settings": VALIDATION.EXPECTED_SETTINGS.copy(),
        "runtime_dependency": {
            "mode": VALIDATION.EXPECTED_RUNTIME_MODE,
            "vcomp_imported": False,
            "source_package_vcomp_present": False,
            "validation_copy_vcomp_present": False,
        },
        "result": {
            "returncode": 0,
            "elapsed_sec": 1.25,
            "output_exists": True,
            "output_bytes": 1024,
            "output_dimensions": [2400, 3320],
            "gpu_device": device,
        },
        "passed": True,
        "redistribution_approved": True,
    }


def clean_account_report(engine_hash: str = "a" * 64) -> dict[str, object]:
    return {
        "schema_version": 1,
        "report_kind": "clean_windows_account",
        "validated_on": "2026-07-27",
        "passed": True,
        "operator_confirmed_separate_account": True,
        "interactive_launch_confirmed": True,
        "developer_tools": {
            "python_installed": False,
            "uv_installed": False,
        },
        "windows": {"version": "10.0.26100", "build": "26100"},
        "archive": {
            "sha256": "b" * 64,
            "engine_sha256": engine_hash,
            "executable_sha256": "c" * 64,
        },
        "smoke_test": {"returncode": 0, "sanitized_path": True},
    }


def release_validation_payload() -> dict[str, object]:
    missing = {
        "passed": False,
        "engine_sha256": None,
        "evidence": None,
    }
    return {
        "schema_version": 3,
        "required": {
            "clean_windows_account": missing.copy(),
            "gpu_families": {
                family: missing.copy() for family in VALIDATION.GPU_FAMILIES
            },
        },
    }


def test_gpu_report_requires_matching_vendor_and_fixed_recipe() -> None:
    summary = VALIDATION.validate_gpu_report(gpu_report(), "nvidia")

    assert summary["engine_sha256"] == "a" * 64
    assert summary["device"] == "NVIDIA Test GPU"
    assert summary["output_dimensions"] == [2400, 3320]

    hybrid = gpu_report()
    hybrid["gpu_inventory"].append({"Name": "Intel Test GPU", "DriverVersion": "4.5.6"})
    with pytest.raises(
        VALIDATION.ValidationError,
        match="execution device does not match intel",
    ):
        VALIDATION.validate_gpu_report(hybrid, "intel")

    unsafe = gpu_report()
    unsafe["runtime_dependency"]["mode"] = "package-local-vcomp"
    with pytest.raises(VALIDATION.ValidationError, match="not release-safe"):
        VALIDATION.validate_gpu_report(unsafe, "nvidia")


def test_clean_account_report_rejects_development_tools() -> None:
    summary = VALIDATION.validate_clean_account_report(clean_account_report())

    assert summary["engine_sha256"] == "a" * 64

    with_python = clean_account_report()
    with_python["developer_tools"]["python_installed"] = True
    with pytest.raises(VALIDATION.ValidationError, match="Python is installed"):
        VALIDATION.validate_clean_account_report(with_python)


def test_record_evidence_rejects_a_different_engine(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(RECORD, "ROOT_DIR", tmp_path)
    validation_path = tmp_path / "packaging/windows/release-validation.json"
    validation_path.parent.mkdir(parents=True)
    validation_path.write_text(
        json.dumps(release_validation_payload()),
        encoding="utf-8",
    )
    evidence_dir = tmp_path / "packaging/windows/validation"
    nvidia_report = tmp_path / "nvidia.json"
    nvidia_report.write_text(json.dumps(gpu_report()), encoding="utf-8")

    evidence_path, summary = RECORD.record_evidence(
        nvidia_report,
        validation_path,
        evidence_dir,
        gpu_family="nvidia",
        clean_account=False,
    )

    assert evidence_path == evidence_dir / "gpu-nvidia.json"
    assert summary["engine_sha256"] == "a" * 64
    recorded = json.loads(validation_path.read_text(encoding="utf-8"))
    assert recorded["required"]["gpu_families"]["nvidia"]["passed"] is True

    intel_report = tmp_path / "intel.json"
    intel_report.write_text(
        json.dumps(gpu_report("d" * 64, "Intel Test GPU")),
        encoding="utf-8",
    )
    with pytest.raises(
        RECORD.ValidationError,
        match="does not match existing passed evidence",
    ):
        RECORD.record_evidence(
            intel_report,
            validation_path,
            evidence_dir,
            gpu_family="intel",
            clean_account=False,
        )
