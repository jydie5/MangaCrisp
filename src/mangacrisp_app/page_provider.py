from __future__ import annotations

import shutil
import tempfile
import threading
import zipfile
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from mangacrisp_app.archive_utils import (
    ArchiveImageMember,
    archive_display_name,
    archive_member_output_path,
    collect_folder_images,
    copy_stream_limited,
    is_archive,
    is_image,
    list_zip_image_members,
    load_sample_pages,
    natural_sort_key,
    validate_archive_members,
)
from mangacrisp_app.branding import CACHE_DIR

PDF_EXTENSIONS = {".pdf"}
PDF_RENDER_DPI = 180
PDF_RENDER_CACHE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
PDF_RENDER_RECENT_PAGE_LIMIT = 48
_PDFIUM_LOCK = threading.RLock()


def is_pdf(path: Path) -> bool:
    return path.suffix.lower() in PDF_EXTENSIONS


def pdf_source_key(pdf_path: Path) -> str:
    stat = pdf_path.stat()
    identity = f"{pdf_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    return sha256(identity.encode("utf-8")).hexdigest()[:24]


def pdf_page_count(pdf_path: Path) -> int:
    try:
        import pypdfium2 as pdfium

        with _PDFIUM_LOCK:
            document = pdfium.PdfDocument(pdf_path)
            try:
                count = len(document)
            finally:
                document.close()
    except Exception as exc:
        raise RuntimeError("PDFを開けません。暗号化または破損している可能性があります。") from exc
    if count <= 0:
        raise RuntimeError("PDFにページがありません。")
    return count


def prune_render_cache(
    cache_root: Path,
    *,
    max_bytes: int = PDF_RENDER_CACHE_LIMIT_BYTES,
    protected: set[Path] | None = None,
) -> int:
    protected_paths = {path.resolve() for path in protected or set()}
    files = [path for path in cache_root.rglob("*.png") if path.is_file()]
    entries: list[tuple[float, int, Path]] = []
    total = 0
    for path in files:
        try:
            stat = path.stat()
        except OSError:
            continue
        total += stat.st_size
        entries.append((stat.st_mtime, stat.st_size, path))
    removed = 0
    for _mtime, size, path in sorted(entries):
        if total <= max(0, max_bytes):
            break
        if path.resolve() in protected_paths:
            continue
        try:
            path.unlink()
        except OSError:
            continue
        total -= size
        removed += 1
    return removed


class PdfPageList(Sequence[Path]):
    def __init__(
        self,
        pdf_path: Path,
        cache_dir: Path | None = None,
        *,
        dpi: int = PDF_RENDER_DPI,
        cache_limit_bytes: int = PDF_RENDER_CACHE_LIMIT_BYTES,
    ) -> None:
        self.pdf_path = pdf_path.expanduser().resolve()
        self.page_count = pdf_page_count(self.pdf_path)
        self.cache_root = (cache_dir or CACHE_DIR / "pdf-render").expanduser()
        self.cache_dir = self.cache_root / pdf_source_key(self.pdf_path)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.dpi = max(72, dpi)
        self.cache_limit_bytes = max(0, cache_limit_bytes)
        self.extracted: dict[int, Path] = {}
        self._materialize_lock = threading.RLock()
        self._render_count = 0
        prune_render_cache(self.cache_root, max_bytes=self.cache_limit_bytes)

    def __len__(self) -> int:
        return self.page_count

    def __getitem__(self, index: int | slice) -> Path | list[Path]:
        if isinstance(index, slice):
            return [self.materialize(item) for item in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        return self.materialize(index)

    def materialize(self, index: int) -> Path:
        output = self.cache_dir / f"{index + 1:06d}.png"
        cached = self.extracted.get(index)
        if cached is not None and cached.is_file():
            cached.touch(exist_ok=True)
            self._remember(index, cached)
            return cached
        if output.is_file():
            output.touch(exist_ok=True)
            self._remember(index, output)
            return output
        with self._materialize_lock:
            if output.is_file():
                output.touch(exist_ok=True)
                self._remember(index, output)
                return output
            self._render_page(index, output)
            self._remember(index, output)
            self._render_count += 1
            if self._render_count == 1 or self._render_count % 16 == 0:
                prune_render_cache(
                    self.cache_root,
                    max_bytes=self.cache_limit_bytes,
                    protected=set(self.extracted.values()),
                )
            return output

    def _remember(self, index: int, path: Path) -> None:
        self.extracted.pop(index, None)
        self.extracted[index] = path
        while len(self.extracted) > PDF_RENDER_RECENT_PAGE_LIMIT:
            oldest = next(iter(self.extracted))
            self.extracted.pop(oldest, None)

    def _render_page(self, index: int, output: Path) -> None:
        try:
            import pypdfium2 as pdfium

            temporary = output.with_suffix(".tmp.png")
            with _PDFIUM_LOCK:
                document = pdfium.PdfDocument(self.pdf_path)
                try:
                    page = document[index]
                    try:
                        bitmap = page.render(
                            scale=self.dpi / 72,
                            draw_annots=True,
                            rev_byteorder=True,
                            prefer_bgrx=True,
                            maybe_alpha=True,
                        )
                        try:
                            image = bitmap.to_pil().convert("RGB")
                            image.save(temporary, format="PNG", optimize=False)
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
                finally:
                    document.close()
            temporary.replace(output)
        except Exception as exc:
            output.with_suffix(".tmp.png").unlink(missing_ok=True)
            raise RuntimeError(f"PDFの{index + 1}ページ目を描画できません。") from exc


class LazyZipPageList(Sequence[Path]):
    def __init__(self, archive_path: Path, temp_dir: Path, members: list[zipfile.ZipInfo]) -> None:
        self.archive_path = archive_path
        self.temp_dir = temp_dir
        self.members = members
        self.extracted: dict[int, Path] = {}

    def __len__(self) -> int:
        return len(self.members)

    def __getitem__(self, index: int | slice) -> Path | list[Path]:
        if isinstance(index, slice):
            return [self.materialize(item) for item in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self.members)
        if index < 0 or index >= len(self.members):
            raise IndexError(index)
        return self.materialize(index)

    def materialize(self, index: int) -> Path:
        cached = self.extracted.get(index)
        if cached is not None:
            return cached
        member = self.members[index]
        output = archive_member_output_path(self.temp_dir, member.filename)
        if output is None:
            raise RuntimeError(f"unsafe archive member: {member.filename}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with (
            zipfile.ZipFile(self.archive_path) as archive,
            archive.open(member) as source,
            output.open("wb") as destination,
        ):
            copy_stream_limited(source, destination)
        resolved = output.resolve()
        self.extracted[index] = resolved
        return resolved


def open_pages_for_viewer(source_path: Path) -> tuple[Sequence[Path], Path | None]:
    source_path = source_path.expanduser().resolve()
    if source_path.is_dir():
        return collect_folder_images(source_path), None
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if is_image(source_path):
        return [source_path], None
    if is_pdf(source_path):
        return PdfPageList(source_path), None
    if not is_archive(source_path):
        raise RuntimeError(f"unsupported sample type: {source_path.suffix}")
    suffix = source_path.suffix.lower()
    if suffix in {".zip", ".cbz"}:
        return open_zip_pages_for_viewer(source_path)
    return load_sample_pages(source_path)


def open_zip_pages_for_viewer(archive_path: Path) -> tuple[LazyZipPageList, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix="mangacrisp_pages_"))
    try:
        safe_members = list_zip_image_members(archive_path)
        safe_names = {member.name for member in safe_members}
        with zipfile.ZipFile(archive_path) as archive:
            members = sorted(
                [
                    info
                    for info in archive.infolist()
                    if not info.is_dir() and archive_display_name(info.filename) in safe_names
                ],
                key=lambda info: natural_sort_key(archive_display_name(info.filename)),
            )
        validate_archive_members(
            [ArchiveImageMember(info.filename, info.file_size, info.compress_size) for info in members]
        )
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return LazyZipPageList(archive_path, temp_dir, members), temp_dir
