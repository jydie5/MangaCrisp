from __future__ import annotations

import io
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from mangacrisp_app.capture.models import CapturePage, CaptureSessionManifest
from mangacrisp_app.capture.package import package_capture_pages
from mangacrisp_app.capture.validation import (
    duplicate_warnings,
    frame_warnings,
    image_sha256,
    perceptual_dhash,
)

CAPTURE_SCHEMA_VERSION = 1


def safe_session_name(value: str) -> str:
    normalized = "".join(character if character.isalnum() or character in "._ -" else "-" for character in value.strip())
    normalized = re.sub(r"\s+", " ", normalized).strip(" .-")
    return normalized[:80] or "Capture"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_json_write(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


class CaptureSession:
    def __init__(self, directory: Path, manifest: CaptureSessionManifest) -> None:
        self.directory = directory
        self.pages_dir = directory / "pages"
        self.undo_dir = directory / ".undo"
        self.manifest_path = directory / "manifest.json"
        self.manifest = manifest
        self.pages_dir.mkdir(parents=True, exist_ok=True)
        self.undo_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create(cls, destination: Path, name: str, *, created_at: datetime | None = None) -> CaptureSession:
        destination = destination.expanduser()
        destination.mkdir(parents=True, exist_ok=True)
        timestamp = (created_at or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
        base = f"{safe_session_name(name)}-capture-{timestamp}"
        directory = destination / base
        suffix = 2
        while directory.exists():
            directory = destination / f"{base}-{suffix}"
            suffix += 1
        directory.mkdir()
        session = cls(
            directory,
            CaptureSessionManifest(
                schema_version=CAPTURE_SCHEMA_VERSION,
                session_name=safe_session_name(name),
                created_at=utc_now_iso(),
            ),
        )
        session.save_manifest()
        return session

    @classmethod
    def open(cls, directory: Path) -> CaptureSession:
        manifest_path = directory / "manifest.json"
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        session = cls(directory, CaptureSessionManifest.from_dict(value))
        session._validate_files()
        return session

    @property
    def pages(self) -> list[CapturePage]:
        return self.manifest.pages

    def save_manifest(self) -> None:
        atomic_json_write(self.manifest_path, self.manifest.to_dict())

    def capture(self, image: Image.Image, *, replace_position: int | None = None) -> CapturePage:
        image = image.convert("RGBA")
        position = replace_position or self._next_position()
        if position < 1 or position > len(self.pages) + 1:
            raise ValueError(f"invalid capture position: {position}")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=False)
        png = buffer.getvalue()
        sha256 = image_sha256(png)
        perceptual_hash = perceptual_dhash(image)
        warnings = frame_warnings(image)
        warnings.extend(
            duplicate_warnings(
                sha256,
                perceptual_hash,
                self.pages,
                exclude_position=replace_position,
            )
        )
        relative = (
            self.pages[self._index_for_position(replace_position)].file
            if replace_position is not None
            else f"pages/{position:06d}.png"
        )
        output = self.directory / relative
        temporary = output.with_name(f".{output.name}.tmp")
        temporary.write_bytes(png)
        os.replace(temporary, output)
        page = CapturePage(
            position=position,
            file=relative,
            sha256=sha256,
            perceptual_hash=perceptual_hash,
            width=image.width,
            height=image.height,
            warnings=tuple(warnings),
        )
        if replace_position is None:
            self.pages.append(page)
        else:
            self.pages[self._index_for_position(replace_position)] = page
        if self.manifest.pixel_size is None:
            self.manifest.pixel_size = {"width": image.width, "height": image.height}
        self.manifest.output = None
        self.save_manifest()
        return page

    def undo_last(self) -> CapturePage:
        if not self.pages:
            raise ValueError("capture session has no page to undo")
        page = self.pages.pop()
        source = self.directory / page.file
        target = self.undo_dir / Path(page.file).name
        target.unlink(missing_ok=True)
        if source.exists():
            shutil.move(source, target)
        self.manifest.output = None
        self.save_manifest()
        return page

    def delete(self, position: int) -> CapturePage:
        index = self._index_for_position(position)
        page = self.pages.pop(index)
        source = self.directory / page.file
        target = self.undo_dir / f"deleted-{Path(page.file).name}"
        target.unlink(missing_ok=True)
        if source.exists():
            shutil.move(source, target)
        self._normalize_positions()
        self.manifest.output = None
        self.save_manifest()
        return page

    def reorder(self, positions: list[int]) -> None:
        if sorted(positions) != list(range(1, len(self.pages) + 1)):
            raise ValueError("reorder positions must contain every page exactly once")
        pages_by_position = {page.position: page for page in self.pages}
        self.manifest.pages = [pages_by_position[position] for position in positions]
        self._normalize_positions(rename_files=False)
        self.manifest.output = None
        self.save_manifest()

    def rotate(self, position: int, degrees: int = 90) -> CapturePage:
        page = self.pages[self._index_for_position(position)]
        source = self.directory / page.file
        with Image.open(source) as image:
            rotated = image.rotate(-degrees, expand=True)
            return self.capture(rotated, replace_position=position)

    def package(self, *, format_name: str = "cbz", output_path: Path | None = None) -> Path:
        normalized = format_name.lower()
        if normalized not in {"cbz", "zip"}:
            raise ValueError(f"unsupported capture package format: {format_name}")
        output = output_path or self.directory / f"{safe_session_name(self.manifest.session_name)}.{normalized}"
        result = package_capture_pages(self.directory, self.pages, output)
        self.manifest.output = {"format": normalized, "file": result.name}
        self.save_manifest()
        return result

    def _next_position(self) -> int:
        return len(self.pages) + 1

    def _index_for_position(self, position: int) -> int:
        for index, page in enumerate(self.pages):
            if page.position == position:
                return index
        raise ValueError(f"capture page does not exist: {position}")

    def _normalize_positions(self, *, rename_files: bool = True) -> None:
        if rename_files:
            staged: list[tuple[Path, Path, CapturePage]] = []
            for index, page in enumerate(self.pages, start=1):
                source = self.directory / page.file
                temporary = self.pages_dir / f".renumber-{index:06d}.png"
                if source.exists():
                    os.replace(source, temporary)
                staged.append((temporary, self.pages_dir / f"{index:06d}.png", page))
            for temporary, target, _page in staged:
                if temporary.exists():
                    os.replace(temporary, target)
        normalized: list[CapturePage] = []
        for index, page in enumerate(self.pages, start=1):
            file = f"pages/{index:06d}.png" if rename_files else page.file
            normalized.append(
                CapturePage(
                    position=index,
                    file=file,
                    sha256=page.sha256,
                    perceptual_hash=page.perceptual_hash,
                    width=page.width,
                    height=page.height,
                    warnings=page.warnings,
                )
            )
        self.manifest.pages = normalized

    def _validate_files(self) -> None:
        directory = self.directory.resolve()
        for page in self.pages:
            path = (self.directory / page.file).resolve()
            if directory not in path.parents or not path.is_file():
                raise ValueError(f"capture page is missing or unsafe: {page.file}")
