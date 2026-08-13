from __future__ import annotations

import os
import zipfile
from pathlib import Path

from mangacrisp_app.capture.models import CapturePage


def package_capture_pages(
    session_dir: Path,
    pages: list[CapturePage],
    output_path: Path,
) -> Path:
    if not pages:
        raise ValueError("cannot package an empty capture session")
    output_path = output_path.expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    temporary_path.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for position, page in enumerate(pages, start=1):
                source = session_dir / page.file
                if not source.is_file():
                    raise FileNotFoundError(source)
                archive.write(source, f"{position:06d}.png")
        with zipfile.ZipFile(temporary_path) as archive:
            expected = [f"{position:06d}.png" for position in range(1, len(pages) + 1)]
            if archive.namelist() != expected or archive.testzip() is not None:
                raise RuntimeError("capture archive verification failed")
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return output_path
