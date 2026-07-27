from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "dist" / "MangaCrisp"
AUDIT_PATH = ROOT_DIR / "dist" / "windows-distribution-audit.json"
MANIFEST_PATH = ROOT_DIR / "dist" / "windows-portable-manifest.json"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT_DIR, check=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_archive(artifact: Path) -> None:
    artifact.unlink(missing_ok=True)
    with zipfile.ZipFile(
        artifact,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(APP_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path("MangaCrisp") / path.relative_to(APP_DIR))


def validate_archive(artifact: Path) -> dict[str, object]:
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        corrupt_member = archive.testzip()
    forbidden = sorted(
        name
        for name in names
        if Path(name).is_absolute()
        or ".." in Path(name).parts
        or {".venv", "__pycache__", "sample", "test"}.intersection(
            part.lower() for part in Path(name).parts
        )
        or Path(name).suffix.lower() in {".pyc", ".pdb"}
    )
    return {
        "entry_count": len(names),
        "corrupt_member": corrupt_member,
        "forbidden_entries": forbidden,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the audited Windows x64 MangaCrisp portable ZIP."
    )
    parser.add_argument(
        "--version",
        default=importlib.metadata.version("mangacrisp"),
    )
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument(
        "--development-baseline",
        action="store_true",
        help="allow a clearly named local ZIP before Real-CUGAN is bundled",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_build:
        run([sys.executable, "scripts/build_windows_app.py"])
    run([sys.executable, "scripts/audit_windows_distribution.py"])
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if not audit.get("baseline_ready"):
        raise SystemExit("Windows distribution baseline audit did not pass")
    if not audit.get("release_ready") and not args.development_baseline:
        raise SystemExit(
            "Windows release audit is incomplete. Use --development-baseline "
            "only for a clearly marked local artifact."
        )

    suffix = "-baseline" if not audit.get("release_ready") else ""
    artifact = (
        ROOT_DIR
        / "dist"
        / f"MangaCrisp-{args.version}-windows-x64-portable{suffix}.zip"
    )
    create_archive(artifact)
    archive_check = validate_archive(artifact)
    if archive_check["corrupt_member"]:
        raise SystemExit(f"corrupt ZIP member: {archive_check['corrupt_member']}")
    if archive_check["forbidden_entries"]:
        raise SystemExit(
            "forbidden ZIP entries:\n"
            + "\n".join(archive_check["forbidden_entries"][:20])
        )

    checksum = sha256_file(artifact)
    checksum_path = artifact.with_suffix(artifact.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {artifact.name}\n", encoding="ascii")
    manifest = {
        "version": args.version,
        "artifact": artifact.name,
        "artifact_sha256": checksum,
        "archive": archive_check,
        "python_required_for_end_user": False,
        "engine_bundled": audit.get("engine_bundled"),
        "baseline_ready": audit.get("baseline_ready"),
        "release_ready": audit.get("release_ready"),
        "development_baseline": not audit.get("release_ready"),
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"artifact: {artifact}")
    print(f"sha256: {checksum}")
    print(f"manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
