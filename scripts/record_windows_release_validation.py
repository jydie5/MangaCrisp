from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from windows_release_validation import (
    GPU_FAMILIES,
    ValidationError,
    load_json_object,
    sha256_file,
    validate_clean_account_report,
    validate_gpu_report,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_VALIDATION_PATH = ROOT_DIR / "packaging" / "windows" / "release-validation.json"
DEFAULT_EVIDENCE_DIR = ROOT_DIR / "packaging" / "windows" / "validation"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify and record Windows release-validation evidence."
    )
    parser.add_argument("--report", type=Path, required=True)
    kind = parser.add_mutually_exclusive_group(required=True)
    kind.add_argument("--gpu-family", choices=GPU_FAMILIES)
    kind.add_argument("--clean-account", action="store_true")
    parser.add_argument("--validation-file", type=Path, default=DEFAULT_VALIDATION_PATH)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    return parser.parse_args()


def passed_engine_hashes(payload: dict[str, Any]) -> set[str]:
    required = payload.get("required")
    if not isinstance(required, dict):
        return set()
    gpu_families = required.get("gpu_families")
    if not isinstance(gpu_families, dict):
        gpu_families = {}
    entries = [
        required.get("clean_windows_account"),
        *(gpu_families.get(family) for family in GPU_FAMILIES),
    ]
    return {
        str(entry["engine_sha256"])
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("passed") is True
        and isinstance(entry.get("engine_sha256"), str)
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def repository_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT_DIR.resolve()).as_posix()
    except ValueError as exc:
        raise ValidationError(
            "evidence directory must be inside the repository"
        ) from exc


def record_evidence(
    report_path: Path,
    validation_path: Path,
    evidence_dir: Path,
    *,
    gpu_family: str | None,
    clean_account: bool,
) -> tuple[Path, dict[str, Any]]:
    report_path = report_path.resolve()
    validation_path = validation_path.resolve()
    evidence_dir = evidence_dir.resolve()
    if not report_path.is_file():
        raise ValidationError(f"report was not found: {report_path}")

    validation = load_json_object(validation_path)
    if validation.get("schema_version") != 3:
        raise ValidationError("release validation schema_version must be 3")
    required = validation.get("required")
    if not isinstance(required, dict):
        raise ValidationError("release validation required section is missing")

    report = load_json_object(report_path)
    if clean_account:
        summary = validate_clean_account_report(report)
        filename = "clean-windows-account.json"
        target_parent = required
        target_key = "clean_windows_account"
    else:
        if gpu_family is None:
            raise ValidationError("GPU family is required")
        summary = validate_gpu_report(report, gpu_family)
        filename = f"gpu-{gpu_family}.json"
        gpu_entries = required.get("gpu_families")
        if not isinstance(gpu_entries, dict):
            raise ValidationError("release validation GPU section is missing")
        target_parent = gpu_entries
        target_key = gpu_family

    existing_hashes = passed_engine_hashes(validation)
    engine_hash = str(summary["engine_sha256"])
    if existing_hashes and existing_hashes != {engine_hash}:
        raise ValidationError(
            "report engine SHA-256 does not match existing passed evidence"
        )

    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / filename
    shutil.copyfile(report_path, evidence_path)
    summary["evidence"] = repository_relative(evidence_path)
    summary["evidence_sha256"] = sha256_file(evidence_path)
    target_parent[target_key] = summary
    atomic_write_json(validation_path, validation)
    return evidence_path, summary


def main() -> None:
    args = parse_args()
    try:
        evidence_path, summary = record_evidence(
            args.report,
            args.validation_file,
            args.evidence_dir,
            gpu_family=args.gpu_family,
            clean_account=args.clean_account,
        )
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"evidence: {evidence_path}")
    print(f"engine_sha256: {summary['engine_sha256']}")
    print(f"validation: {args.validation_file.resolve()}")


if __name__ == "__main__":
    main()
