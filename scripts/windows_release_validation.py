from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

GPU_FAMILIES = ("nvidia", "intel", "amd")
GPU_VENDOR_MARKERS = {
    "nvidia": ("nvidia",),
    "intel": ("intel",),
    "amd": ("amd", "radeon", "advanced micro devices"),
}
EXPECTED_DEMO_ARCHIVE = "Pepper-and-Carrot v01 The-Potion-of-Flight.zip"
EXPECTED_DEMO_SHA256 = (
    "eae7b064a393cdfda43325f97c4790b92d72c339003de4467f62985c8e9fce07"
)
EXPECTED_SETTINGS = {
    "model": "models-se",
    "scale": 2,
    "noise": 0,
    "tile": 0,
    "tta": False,
}
EXPECTED_RUNTIME_MODE = "windows-system-api-and-vulkan-loader"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ValidationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSON report {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"report root must be an object: {path.name}")
    return payload


def require_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValidationError(f"{key} must be an object")
    return value


def require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise ValidationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def require_dimensions(value: object, label: str) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(not isinstance(item, int) or item <= 0 for item in value)
    ):
        raise ValidationError(f"{label} must contain two positive integers")
    return value[0], value[1]


def gpu_name_matches_family(name: str, family: str) -> bool:
    return any(marker in name.lower() for marker in GPU_VENDOR_MARKERS[family])


def matching_gpu(
    inventory: object,
    family: str,
) -> tuple[str, str | None]:
    if family not in GPU_FAMILIES:
        raise ValidationError(f"unsupported GPU family: {family}")
    if not isinstance(inventory, list):
        raise ValidationError("gpu_inventory must be a list")
    for item in inventory:
        if not isinstance(item, dict):
            continue
        name = item.get("Name")
        if not isinstance(name, str):
            continue
        if gpu_name_matches_family(name, family):
            driver = item.get("DriverVersion")
            return name, driver if isinstance(driver, str) else None
    raise ValidationError(f"gpu_inventory does not contain a matching {family} device")


def validate_gpu_report(
    payload: dict[str, Any],
    family: str,
) -> dict[str, Any]:
    if payload.get("schema_version") != 2:
        raise ValidationError("GPU report schema_version must be 2")
    if payload.get("passed") is not True:
        raise ValidationError("GPU validation did not pass")
    if payload.get("redistribution_approved") is not True:
        raise ValidationError("GPU report did not validate redistribution provenance")

    engine = require_object(payload, "engine")
    engine_hash = require_sha256(engine.get("sha256"), "engine.sha256")
    if engine.get("provenance_hash_verified") is not True:
        raise ValidationError("engine provenance hash was not verified")
    if engine.get("provenance_hash") != engine_hash:
        raise ValidationError("engine provenance hash does not match the engine")

    input_record = require_object(payload, "input")
    if input_record.get("archive") != EXPECTED_DEMO_ARCHIVE:
        raise ValidationError("GPU report does not use the fixed demo archive")
    if input_record.get("archive_sha256") != EXPECTED_DEMO_SHA256:
        raise ValidationError("GPU report demo archive hash does not match")
    member = input_record.get("member")
    if not isinstance(member, str) or not member:
        raise ValidationError("GPU report demo member is missing")
    input_dimensions = require_dimensions(
        input_record.get("dimensions"),
        "input.dimensions",
    )

    settings = require_object(payload, "settings")
    if settings != EXPECTED_SETTINGS:
        raise ValidationError("GPU report settings do not match the fixed recipe")

    runtime = require_object(payload, "runtime_dependency")
    if runtime.get("mode") != EXPECTED_RUNTIME_MODE:
        raise ValidationError("GPU report runtime dependency mode is not release-safe")
    if runtime.get("vcomp_imported") is not False:
        raise ValidationError("GPU report engine imports vcomp")
    if runtime.get("source_package_vcomp_present") is not False:
        raise ValidationError("GPU report source package contains vcomp")
    if runtime.get("validation_copy_vcomp_present") is not False:
        raise ValidationError("GPU report validation copy contains vcomp")

    result = require_object(payload, "result")
    if result.get("returncode") != 0 or result.get("output_exists") is not True:
        raise ValidationError("GPU report output was not produced successfully")
    output_bytes = result.get("output_bytes")
    if not isinstance(output_bytes, int) or output_bytes <= 0:
        raise ValidationError("GPU report output is empty")
    output_dimensions = require_dimensions(
        result.get("output_dimensions"),
        "result.output_dimensions",
    )
    scale = EXPECTED_SETTINGS["scale"]
    expected_output = (
        input_dimensions[0] * scale,
        input_dimensions[1] * scale,
    )
    if output_dimensions != expected_output:
        raise ValidationError("GPU report output dimensions do not match the recipe")
    elapsed_sec = result.get("elapsed_sec")
    if not isinstance(elapsed_sec, (int, float)) or elapsed_sec < 0:
        raise ValidationError("GPU report elapsed time is invalid")

    executed_device = result.get("gpu_device")
    if not isinstance(executed_device, str) or not executed_device:
        raise ValidationError("GPU report execution device is missing")
    if not gpu_name_matches_family(executed_device, family):
        raise ValidationError(f"GPU report execution device does not match {family}")
    _, driver_version = matching_gpu(payload.get("gpu_inventory"), family)
    validated_on = payload.get("validated_on")
    if not isinstance(validated_on, str) or not validated_on:
        raise ValidationError("GPU report validated_on date is missing")

    return {
        "passed": True,
        "engine_sha256": engine_hash,
        "device": executed_device,
        "driver_version": driver_version,
        "demo": f"{EXPECTED_DEMO_ARCHIVE}/{member}",
        "input_dimensions": list(input_dimensions),
        "output_dimensions": list(output_dimensions),
        "elapsed_sec": round(float(elapsed_sec), 3),
        "validated_on": validated_on,
    }


def validate_clean_account_report(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != 1:
        raise ValidationError("clean-account report schema_version must be 1")
    if payload.get("report_kind") != "clean_windows_account":
        raise ValidationError("report is not a clean Windows account report")
    if payload.get("passed") is not True:
        raise ValidationError("clean Windows account validation did not pass")
    if payload.get("operator_confirmed_separate_account") is not True:
        raise ValidationError("separate Windows account was not confirmed")
    if payload.get("interactive_launch_confirmed") is not True:
        raise ValidationError("interactive double-click launch was not confirmed")

    developer_tools = require_object(payload, "developer_tools")
    if developer_tools.get("python_installed") is not False:
        raise ValidationError("Python is installed in the clean account")
    if developer_tools.get("uv_installed") is not False:
        raise ValidationError("uv is installed in the clean account")

    archive = require_object(payload, "archive")
    require_sha256(archive.get("sha256"), "archive.sha256")
    engine_hash = require_sha256(archive.get("engine_sha256"), "archive.engine_sha256")
    executable_hash = require_sha256(
        archive.get("executable_sha256"),
        "archive.executable_sha256",
    )

    smoke = require_object(payload, "smoke_test")
    if smoke.get("returncode") != 0:
        raise ValidationError("clean-account packaged smoke test failed")
    if smoke.get("sanitized_path") is not True:
        raise ValidationError("clean-account smoke test did not sanitize PATH")

    validated_on = payload.get("validated_on")
    if not isinstance(validated_on, str) or not validated_on:
        raise ValidationError("clean-account validated_on date is missing")

    windows = require_object(payload, "windows")
    return {
        "passed": True,
        "engine_sha256": engine_hash,
        "archive_sha256": archive["sha256"],
        "executable_sha256": executable_hash,
        "windows_version": windows.get("version"),
        "windows_build": windows.get("build"),
        "validated_on": validated_on,
    }


def safe_evidence_path(root_dir: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValidationError("evidence path is missing")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValidationError("evidence path must stay inside the repository")
    resolved = (root_dir / relative).resolve()
    root = root_dir.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValidationError("evidence path escapes the repository")
    return resolved


def audit_release_validation(
    validation_path: Path,
    root_dir: Path,
    engine_hash: str | None,
    executable_hash: str | None,
) -> dict[str, Any]:
    try:
        payload = load_json_object(validation_path)
    except ValidationError as exc:
        return {"ready": False, "errors": [str(exc)], "checks": {}}
    if payload.get("schema_version") != 3:
        return {
            "ready": False,
            "errors": ["release validation schema_version must be 3"],
            "checks": {},
        }

    required = payload.get("required")
    if not isinstance(required, dict):
        return {
            "ready": False,
            "errors": ["release validation required section is missing"],
            "checks": {},
        }
    gpu_families = required.get("gpu_families")
    if not isinstance(gpu_families, dict):
        gpu_families = {}
    checks = {
        "clean_windows_account": required.get("clean_windows_account", {}),
        **{f"gpu_{family}": gpu_families.get(family, {}) for family in GPU_FAMILIES},
    }

    errors: list[str] = []
    for label, entry in checks.items():
        if not isinstance(entry, dict) or entry.get("passed") is not True:
            errors.append(f"{label} has not passed")
            continue
        if entry.get("engine_sha256") != engine_hash:
            errors.append(f"{label} was not validated against the bundled engine")
            continue
        try:
            evidence_path = safe_evidence_path(root_dir, entry.get("evidence"))
            expected_evidence_hash = require_sha256(
                entry.get("evidence_sha256"),
                f"{label}.evidence_sha256",
            )
            if not evidence_path.is_file():
                raise ValidationError("evidence file is missing")
            if sha256_file(evidence_path) != expected_evidence_hash:
                raise ValidationError("evidence file hash does not match")
            evidence = load_json_object(evidence_path)
            if label == "clean_windows_account":
                summary = validate_clean_account_report(evidence)
                if summary["executable_sha256"] != executable_hash:
                    raise ValidationError("evidence application hash does not match")
            else:
                summary = validate_gpu_report(evidence, label.removeprefix("gpu_"))
            if summary["engine_sha256"] != engine_hash:
                raise ValidationError("evidence engine hash does not match")
            for key, value in summary.items():
                if entry.get(key) != value:
                    raise ValidationError(f"recorded {key} does not match evidence")
        except ValidationError as exc:
            errors.append(f"{label} evidence is invalid: {exc}")

    return {
        "ready": not errors,
        "errors": errors,
        "checks": checks,
    }
