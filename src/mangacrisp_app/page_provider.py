from __future__ import annotations

import os
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
from mangacrisp_app.cache_utils import prune_png_cache

PDF_EXTENSIONS = {".pdf"}
PDF_RENDER_DPI = 180
PDF_RENDER_CACHE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
PDF_RENDER_CACHE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
PDF_RENDER_RECENT_PAGE_LIMIT = 48
_PDFIUM_LOCK = threading.RLock()


def is_pdf(path: Path) -> bool:
    return path.suffix.lower() in PDF_EXTENSIONS


def pdf_source_key(pdf_path: Path) -> str:
    stat = pdf_path.stat()
    identity = f"{pdf_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    return sha256(identity.encode("utf-8")).hexdigest()[:24]


def pdf_render_cache_dir(
    pdf_path: Path,
    cache_dir: Path | None = None,
    *,
    dpi: int = PDF_RENDER_DPI,
    source_key: str | None = None,
) -> Path:
    """Return the rendered-page directory for one PDF source and DPI.

    The historical default-DPI directory is kept in place so existing render
    caches remain usable. Non-default render sizes live below that source
    directory and cannot overwrite the default render.
    """
    root = (cache_dir or CACHE_DIR / "pdf-render").expanduser()
    fingerprint = source_key or pdf_source_key(pdf_path)
    normalized_dpi = max(72, dpi)
    base = root / fingerprint
    return base if normalized_dpi == PDF_RENDER_DPI else base / f"dpi-{normalized_dpi}"


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
    max_age_seconds: int | None = PDF_RENDER_CACHE_MAX_AGE_SECONDS,
    protected: set[Path] | None = None,
    now: float | None = None,
) -> int:
    return prune_png_cache(
        cache_root,
        max_bytes=max_bytes,
        max_age_seconds=max_age_seconds,
        protected=protected,
        now=now,
    )


def _pdf_page_identity(source_key: str, dpi: int, index: int) -> str:
    return f"pdf:{source_key}:dpi-{dpi}:page-{index}"


class PdfPageIdentityProvider:
    """Expose PDF cache identities without opening or rendering the PDF.

    The bookshelf keeps the recorded page count for an imported PDF.  That
    count is enough to enumerate disposable AI-cache keys even when the PDF
    has since become unreadable, while the source fingerprint still prevents
    deleting results for a different file at the same path.
    """

    def __init__(
        self,
        pdf_path: Path,
        page_count: int,
        *,
        dpi: int = PDF_RENDER_DPI,
        source_key: str | None = None,
    ) -> None:
        self.pdf_path = pdf_path.expanduser().resolve()
        self._pdf_source_key = source_key or pdf_source_key(self.pdf_path)
        self.page_count = max(0, int(page_count))
        self.dpi = max(72, dpi)

    def __len__(self) -> int:
        return self.page_count

    def cache_source_identity(self, index: int) -> str:
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        return _pdf_page_identity(self._pdf_source_key, self.dpi, index)


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
        self._pdf_source_key = pdf_source_key(self.pdf_path)
        self.page_count = pdf_page_count(self.pdf_path)
        self.cache_root = (cache_dir or CACHE_DIR / "pdf-render").expanduser()
        self.dpi = max(72, dpi)
        self.cache_dir = pdf_render_cache_dir(
            self.pdf_path,
            self.cache_root,
            dpi=self.dpi,
            source_key=self._pdf_source_key,
        )
        self.cache_limit_bytes = max(0, cache_limit_bytes)
        self.extracted: dict[int, Path] = {}
        self._materialize_lock = threading.RLock()
        self._touched_paths: set[Path] = set()
        self._render_count = 0
        prune_render_cache(self.cache_root, max_bytes=self.cache_limit_bytes)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

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

    def cache_source_identity(self, index: int) -> str:
        """Return an identity independent of the rendered PNG's access mtime."""
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        return _pdf_page_identity(self._pdf_source_key, self.dpi, index)

    def materialize(self, index: int) -> Path:
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        output = self.cache_dir / f"{index + 1:06d}.png"
        with self._materialize_lock:
            cached = self.extracted.get(index)
            if cached is not None:
                if self._touch_once(cached):
                    self._remember(index, cached)
                    return cached
                self.extracted.pop(index, None)
                self._touched_paths.discard(cached)

            if self._touch_once(output):
                self._remember(index, output)
                return output

            self._touched_paths.discard(output)
            self._render_page(index, output)
            # A newly rendered file already has a current mtime. Mark it as
            # touched so the next viewer lookup does not change that mtime.
            self._touched_paths.add(output)
            self._remember(index, output)
            self._render_count += 1
            if self._render_count == 1 or self._render_count % 16 == 0:
                # Take the protected set while the provider state is locked;
                # pruning must not race a concurrent materialization.
                protected = set(self.extracted.values())
                prune_render_cache(
                    self.cache_root,
                    max_bytes=self.cache_limit_bytes,
                    protected=protected,
                )
            return output

    def _touch_once(self, path: Path) -> bool:
        """Touch an existing cache file once without recreating a missing one."""
        if path in self._touched_paths:
            if path.is_file():
                return True
            self._touched_paths.discard(path)
            return False
        if not path.is_file():
            return False
        try:
            os.utime(path, None)
        except OSError:
            self._touched_paths.discard(path)
            return False
        if not path.is_file():
            self._touched_paths.discard(path)
            return False
        self._touched_paths.add(path)
        return True

    def _remember(self, index: int, path: Path) -> None:
        self.extracted.pop(index, None)
        self.extracted[index] = path
        while len(self.extracted) > PDF_RENDER_RECENT_PAGE_LIMIT:
            oldest, oldest_path = next(iter(self.extracted.items()))
            self.extracted.pop(oldest, None)
            self._touched_paths.discard(oldest_path)

    def _render_page(self, index: int, output: Path) -> None:
        try:
            import pypdfium2 as pdfium

            temporary = output.with_suffix(".tmp.png")
            temporary.parent.mkdir(parents=True, exist_ok=True)
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
        self.archive_path = archive_path.expanduser().resolve()
        self.temp_dir = temp_dir
        self.members = members
        self.extracted: dict[int, Path] = {}
        self._materialize_lock = threading.RLock()
        stat = self.archive_path.stat()
        self._archive_fingerprint = f"{self.archive_path}:{stat.st_size}:{stat.st_mtime_ns}"

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

    def cache_source_identity(self, index: int) -> str:
        """Return a stable identity for an archive member, excluding temp_dir."""
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        member = self.members[index]
        member_name = archive_display_name(member.filename)
        return (
            f"zip:{self._archive_fingerprint}:index={index}:member={member_name}:"
            f"crc={member.CRC}:size={member.file_size}"
        )

    def materialize(self, index: int) -> Path:
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        with self._materialize_lock:
            cached = self.extracted.get(index)
            if cached is not None:
                if cached.is_file():
                    return cached
                self.extracted.pop(index, None)

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
