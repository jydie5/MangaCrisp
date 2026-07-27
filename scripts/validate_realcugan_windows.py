from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from build_realcugan_windows import (
    ENGINE_NAME,
    PACKAGE_DIR,
    executable_imports,
)
from PIL import Image

from mangacrisp_app.engine_utils import run_realcugan
from mangacrisp_app.platform import subprocess_window_kwargs

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENGINE = PACKAGE_DIR / ENGINE_NAME
DEFAULT_DEMO = ROOT_DIR / "demo" / "Pepper-and-Carrot v01 The-Potion-of-Flight.zip"
DEFAULT_REPORT = ROOT_DIR / "build" / "windows" / "realcugan-validation.json"
IMAGE_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
GPU_DEVICE_PATTERN = re.compile(r"^\[\d+\s+(.+?)\]\s", re.MULTILINE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reported_gpu_device(stdout: str) -> str | None:
    match = GPU_DEVICE_PATTERN.search(stdout)
    return match.group(1).strip() if match else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the pinned Windows Real-CUGAN engine on one demo page."
    )
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--demo", type=Path, default=DEFAULT_DEMO)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--gpu-label", default="")
    parser.add_argument(
        "--system-vcomp-only",
        action="store_true",
        help="compatibility check: reject package-local vcomp140.dll when imported",
    )
    return parser.parse_args()


def windows_gpu_inventory() -> list[dict[str, object]]:
    command = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,DriverVersion | "
        "ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
        **subprocess_window_kwargs(),
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else [payload]


def first_demo_image(archive_path: Path, destination: Path) -> tuple[str, Path]:
    with zipfile.ZipFile(archive_path) as archive:
        member = next(
            (
                info
                for info in archive.infolist()
                if not info.is_dir()
                and Path(info.filename).suffix.lower() in IMAGE_SUFFIXES
            ),
            None,
        )
        if member is None:
            raise RuntimeError(f"demo archive has no supported images: {archive_path}")
        output = destination / f"input{Path(member.filename).suffix.lower()}"
        with archive.open(member) as source, output.open("wb") as target:
            target.write(source.read())
    return member.filename, output


def main() -> None:
    args = parse_args()
    engine = args.engine.resolve()
    demo = args.demo.resolve()
    report = args.report.resolve()
    if not engine.is_file():
        raise SystemExit(
            f"Real-CUGAN was not found: {engine}\n"
            "Run: uv run python scripts/build_realcugan_windows.py"
        )
    if not demo.is_file():
        raise SystemExit(f"demo archive was not found: {demo}")
    imports = executable_imports(engine)
    vcomp_imported = any(name.lower().startswith("vcomp") for name in imports)
    provenance_path = engine.parent / "realcugan-provenance.json"
    provenance: dict[str, object] = {}
    if provenance_path.is_file():
        try:
            loaded = json.loads(provenance_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                provenance = loaded
        except (OSError, json.JSONDecodeError):
            pass
    provenance_engine = provenance.get("engine", {})
    provenance_hash = (
        provenance_engine.get("sha256") if isinstance(provenance_engine, dict) else None
    )

    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    system_vcomp = system_root / "System32" / "vcomp140.dll"
    if args.system_vcomp_only and vcomp_imported and not system_vcomp.is_file():
        raise SystemExit(
            "system vcomp140.dll was not found; install the supported "
            "Microsoft Visual C++ x64 Redistributable"
        )

    with TemporaryDirectory(prefix="mangacrisp-realcugan-validation-") as temporary:
        temporary_path = Path(temporary)
        engine_to_run = engine
        if args.system_vcomp_only and vcomp_imported:
            engine_copy = temporary_path / "engine"
            shutil.copytree(engine.parent, engine_copy)
            (engine_copy / "vcomp140.dll").unlink(missing_ok=True)
            engine_to_run = engine_copy / engine.name
        validation_vcomp_present = (engine_to_run.parent / "vcomp140.dll").is_file()

        member_name, input_path = first_demo_image(demo, temporary_path)
        output_path = temporary_path / "output.png"
        previous_engine = os.environ.get("MANGACRISP_REALCUGAN_PATH")
        os.environ["MANGACRISP_REALCUGAN_PATH"] = str(engine_to_run)
        try:
            result = run_realcugan(
                input_path,
                output_path,
                scale=2,
                noise=0,
                tile=0,
                model="models-se",
                tta=False,
            )
        finally:
            if previous_engine is None:
                os.environ.pop("MANGACRISP_REALCUGAN_PATH", None)
            else:
                os.environ["MANGACRISP_REALCUGAN_PATH"] = previous_engine

        with Image.open(input_path) as input_image:
            input_size = input_image.size
        if output_path.is_file():
            with Image.open(output_path) as output_image:
                output_size = output_image.size
        else:
            output_size = None

    engine_hash = sha256_file(engine)
    payload = {
        "schema_version": 2,
        "validated_on": datetime.now(UTC).date().isoformat(),
        "gpu_label": args.gpu_label,
        "gpu_inventory": windows_gpu_inventory(),
        "engine": {
            "release": "20220728",
            "filename": engine.name,
            "sha256": engine_hash,
            "imports": imports,
            "provenance_hash": provenance_hash,
            "provenance_hash_verified": provenance_hash == engine_hash,
        },
        "input": {
            "archive": demo.name,
            "archive_sha256": sha256_file(demo),
            "member": member_name,
            "dimensions": list(input_size),
        },
        "settings": {
            "model": "models-se",
            "scale": 2,
            "noise": 0,
            "tile": 0,
            "tta": False,
        },
        "runtime_dependency": {
            "mode": (
                "windows-system-api-and-vulkan-loader"
                if not vcomp_imported
                else "system-vcomp"
                if args.system_vcomp_only
                else "package-local-vcomp"
            ),
            "imports": imports,
            "vcomp_imported": vcomp_imported,
            "source_package_vcomp_present": (engine.parent / "vcomp140.dll").is_file(),
            "validation_copy_vcomp_present": validation_vcomp_present,
            "system_vcomp_present": system_vcomp.is_file(),
            "system_vcomp_sha256": (
                sha256_file(system_vcomp) if system_vcomp.is_file() else None
            ),
        },
        "result": {
            "returncode": result.returncode,
            "elapsed_sec": round(result.elapsed_sec, 3),
            "output_exists": result.output_exists,
            "output_bytes": result.output_size,
            "output_dimensions": list(output_size) if output_size else None,
            "gpu_device": reported_gpu_device(result.stdout),
            "stdout": result.stdout,
        },
        "passed": (
            result.returncode == 0
            and result.output_exists
            and result.output_size > 0
            and output_size == (input_size[0] * 2, input_size[1] * 2)
        ),
        "redistribution_approved": (
            provenance.get("redistribution_approved") is True
            and provenance_hash == engine_hash
            and not vcomp_imported
        ),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"report: {report}")
    print(
        f"passed={payload['passed']} elapsed_sec={result.elapsed_sec:.3f} "
        f"input={input_size[0]}x{input_size[1]} "
        f"output={output_size[0] if output_size else 0}x"
        f"{output_size[1] if output_size else 0}"
    )
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
