from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import windows_release_validation as RELEASE_VALIDATION

SCRIPT_PATH = SCRIPTS_DIR / "audit_windows_distribution.py"
SPEC = importlib.util.spec_from_file_location(
    "audit_windows_distribution",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def gpu_report(engine_hash: str, device: str) -> dict[str, object]:
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
            "archive": "Pepper-and-Carrot v01 The-Potion-of-Flight.zip",
            "archive_sha256": (
                "eae7b064a393cdfda43325f97c4790b92d72c339003de4467f62985c8e9fce07"
            ),
            "member": "01.jpg",
            "dimensions": [1200, 1660],
        },
        "settings": {
            "model": "models-se",
            "scale": 2,
            "noise": 0,
            "tile": 0,
            "tta": False,
        },
        "runtime_dependency": {
            "mode": "windows-system-api-and-vulkan-loader",
            "vcomp_imported": False,
            "source_package_vcomp_present": False,
            "validation_copy_vcomp_present": False,
        },
        "result": {
            "returncode": 0,
            "elapsed_sec": 1.0,
            "output_exists": True,
            "output_bytes": 1024,
            "output_dimensions": [2400, 3320],
            "gpu_device": device,
        },
        "passed": True,
        "redistribution_approved": True,
    }


def clean_account_report(engine_hash: str) -> dict[str, object]:
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
        "windows": {
            "version": "10.0.26100",
            "build": "26100",
        },
        "archive": {
            "sha256": "c" * 64,
            "engine_sha256": engine_hash,
            "executable_sha256": "d" * 64,
        },
        "smoke_test": {
            "returncode": 0,
            "sanitized_path": True,
        },
    }


def evidence_entry(
    root: Path,
    relative_path: str,
    payload: dict[str, object],
    engine_hash: str,
) -> dict[str, object]:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    if payload.get("report_kind") == "clean_windows_account":
        summary = RELEASE_VALIDATION.validate_clean_account_report(payload)
    else:
        family = Path(relative_path).stem.removeprefix("gpu-")
        summary = RELEASE_VALIDATION.validate_gpu_report(payload, family)
    return {
        **summary,
        "evidence": relative_path,
        "evidence_sha256": AUDIT.sha256_file(path),
    }


def validation_payload(root: Path, engine_hash: str) -> dict[str, object]:
    base = "packaging/windows/validation"
    clean_account = evidence_entry(
        root,
        f"{base}/clean-windows-account.json",
        clean_account_report(engine_hash),
        engine_hash,
    )
    gpu_families = {
        family: evidence_entry(
            root,
            f"{base}/gpu-{family}.json",
            gpu_report(engine_hash, device),
            engine_hash,
        )
        for family, device in (
            ("nvidia", "NVIDIA Test GPU"),
            ("intel", "Intel Test GPU"),
            ("amd", "AMD Radeon Test GPU"),
        )
    }
    return {
        "schema_version": 3,
        "required": {
            "clean_windows_account": clean_account,
            "gpu_families": gpu_families,
        },
    }


def test_release_validation_requires_bundled_engine_hash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    engine_hash = "a" * 64
    validation_path = tmp_path / "release-validation.json"
    payload = validation_payload(tmp_path, engine_hash)
    validation_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(AUDIT, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(AUDIT, "RELEASE_VALIDATION_PATH", validation_path)

    passed = AUDIT.release_validation_audit(engine_hash, "d" * 64)

    assert passed["ready"] is True
    assert passed["errors"] == []

    wrong_application = AUDIT.release_validation_audit(engine_hash, "e" * 64)
    assert wrong_application["ready"] is False
    assert any(
        "clean_windows_account evidence is invalid: evidence application hash" in error
        for error in wrong_application["errors"]
    )

    payload["required"]["gpu_families"]["intel"]["engine_sha256"] = "b" * 64
    validation_path.write_text(json.dumps(payload), encoding="utf-8")

    failed = AUDIT.release_validation_audit(engine_hash, "d" * 64)

    assert failed["ready"] is False
    assert "gpu_intel was not validated against the bundled engine" in failed["errors"]
