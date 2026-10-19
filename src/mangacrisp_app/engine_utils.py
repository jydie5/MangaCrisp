from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

from mangacrisp_app.platform import engine_executable_names, subprocess_window_kwargs

ROOT_DIR = Path(__file__).resolve().parents[2]
ENGINES_DIR = ROOT_DIR / "test" / "engines"
PRO_SYNC_GAP = 1


def bundled_root() -> Path | None:
    bundle_root = getattr(sys, "_MEIPASS", None)
    return Path(bundle_root) if bundle_root else None


@dataclass
class EngineRunResult:
    engine: str
    executable: str
    input: str
    output: str
    returncode: int
    elapsed_sec: float
    stdout: str
    output_exists: bool
    output_size: int


def realcugan_executable() -> Path | None:
    frozen_root = bundled_root()
    env_path = os.environ.get("MANGACRISP_REALCUGAN_PATH")
    package_names = [
        "realcugan-ncnn-vulkan",
        "realcugan-ncnn-vulkan-20220728-macos",
        "realcugan-ncnn-vulkan-20220728-windows",
        "realcugan-ncnn-vulkan-20220728-ubuntu",
    ]
    package_dirs = [ENGINES_DIR / name for name in package_names]
    package_dirs.extend(ROOT_DIR / parent / name for parent in ("engines", "tools") for name in package_names)
    if frozen_root is not None:
        package_dirs[:0] = [frozen_root / "engines" / name for name in package_names]
    candidates = [Path(env_path).expanduser()] if env_path else []
    candidates.extend(
        package_dir / executable_name
        for package_dir in package_dirs
        for executable_name in engine_executable_names("realcugan-ncnn-vulkan")
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def run_realcugan(
    input_path: Path,
    output_path: Path,
    *,
    scale: int = 2,
    noise: int = 1,
    tile: int = 0,
    model: str = "models-se",
    tta: bool = False,
) -> EngineRunResult:
    executable = realcugan_executable()
    if executable is None:
        raise FileNotFoundError("realcugan-ncnn-vulkan executable was not found")
    executable = executable.expanduser().resolve()
    input_path = input_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    expected_size = _expected_output_size(input_path, scale)
    with tempfile.TemporaryDirectory(
        prefix=f".mangacrisp-{output_path.stem}-",
        dir=str(output_path.parent),
    ) as temporary_directory:
        temporary_output = Path(temporary_directory) / output_path.name
        command = [
            str(executable),
            "-i",
            str(input_path),
            "-o",
            str(temporary_output),
            "-s",
            str(scale),
            "-n",
            str(noise),
            "-t",
            str(tile),
            "-m",
            model,
            "-f",
            "png",
        ]
        if model == "models-pro":
            # The engine's default very-rough sync gap (-c 3) can corrupt pro
            # output with strong false colors on screentone-heavy pages, even
            # when the process succeeds. Keep accurate cross-tile statistics.
            # viewer.current_parameter_key also versions the pro cache for this.
            command.extend(["-c", str(PRO_SYNC_GAP)])
        if tta:
            command.append("-x")
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=str(executable.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            check=False,
            **subprocess_window_kwargs(),
        )
        elapsed = time.perf_counter() - started
        returncode = completed.returncode
        stdout = (completed.stdout or "").strip()
        if returncode == 0:
            reason = _invalid_output_reason(temporary_output, expected_size)
            if reason is None:
                try:
                    temporary_output.replace(output_path)
                except OSError:
                    returncode = 1
                    stdout = _append_reason(stdout, "Could not publish the correction result to the cache.")
            else:
                returncode = 1
                stdout = _append_reason(stdout, reason)

    output_exists = output_path.is_file()
    try:
        output_size = output_path.stat().st_size if output_exists else 0
    except OSError:
        output_exists = False
        output_size = 0
    return EngineRunResult(
        engine="realcugan-ncnn-vulkan",
        executable=str(executable),
        input=str(input_path),
        output=str(output_path),
        returncode=returncode,
        elapsed_sec=elapsed,
        stdout=stdout,
        output_exists=output_exists,
        output_size=output_size,
    )


def _expected_output_size(input_path: Path, scale: int) -> tuple[int, int] | None:
    try:
        with Image.open(input_path) as image:
            return image.width * scale, image.height * scale
    except (EOFError, OSError, SyntaxError, TypeError, ValueError, Image.DecompressionBombError):
        return None


def _invalid_output_reason(path: Path, expected_size: tuple[int, int] | None) -> str | None:
    if not path.is_file():
        return "Real-CUGAN did not produce a PNG."
    if expected_size is None:
        return "Could not determine the input image dimensions."
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            if image.format != "PNG":
                return "Engine output is not a PNG."
            if image.size != expected_size:
                return "Engine output dimensions do not match the expected size."
    except (EOFError, OSError, SyntaxError, TypeError, ValueError, Image.DecompressionBombError):
        return "Engine output is a corrupt PNG."
    return None


def _append_reason(stdout: str, reason: str) -> str:
    message = f"[MangaCrisp] {reason}"
    return f"{stdout}\n{message}" if stdout else message


def write_results_json(path: Path, results: list[EngineRunResult], extra: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "extra": extra or {},
        "results": [asdict(result) for result in results],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
