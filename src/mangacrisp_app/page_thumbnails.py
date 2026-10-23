"""Lazy, reader-independent thumbnail decoding for the page overview."""

from __future__ import annotations

import os
import tempfile
import zipfile
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QImageReader

from mangacrisp_app.archive_utils import (
    ArchiveImageMember,
    copy_stream_limited,
    validate_archive_members,
)
from mangacrisp_app.page_provider import _PDFIUM_LOCK, LazyZipPageList, PdfPageList

THUMBNAIL_SIZE = QSize(128, 180)
THUMBNAIL_CACHE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class _ZipThumbnailMember:
    """An immutable locator for a ZIP member, including duplicate names."""

    name: str
    header_offset: int
    file_size: int
    compressed_size: int
    crc: int


@dataclass(frozen=True)
class ThumbnailSource:
    """Immutable source description that never uses the reader's temp paths."""

    kind: str
    paths: tuple[Path, ...] = ()
    page_count: int = 0
    pdf_path: Path | None = None
    archive_path: Path | None = None
    members: tuple[_ZipThumbnailMember, ...] = ()

    @classmethod
    def from_pages(cls, pages: Sequence[Path]) -> ThumbnailSource:
        if isinstance(pages, PdfPageList):
            return cls("pdf", pdf_path=pages.pdf_path, page_count=len(pages))
        if isinstance(pages, LazyZipPageList):
            return cls(
                "zip",
                archive_path=pages.archive_path,
                members=tuple(
                    _ZipThumbnailMember(
                        member.filename,
                        member.header_offset,
                        member.file_size,
                        member.compress_size,
                        member.CRC,
                    )
                    for member in pages.members
                ),
            )
        return cls("images", paths=tuple(Path(path) for path in pages))

    def __len__(self) -> int:
        if self.kind == "pdf":
            return self.page_count
        if self.kind == "zip":
            return len(self.members)
        return len(self.paths)

    def decode(self, index: int, size: QSize = THUMBNAIL_SIZE) -> QImage:
        if index < 0 or index >= len(self):
            raise IndexError(index)
        if self.kind == "pdf":
            return self._decode_pdf(index, size)
        if self.kind == "zip":
            return self._decode_zip(index, size)
        return self._decode_image_file(self.paths[index], size)

    @staticmethod
    def _scale(image: QImage, size: QSize) -> QImage:
        return image.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _decode_zip(self, index: int, size: QSize) -> QImage:
        if self.archive_path is None:
            raise RuntimeError("archive source unavailable")
        with zipfile.ZipFile(self.archive_path) as archive:
            member = self._zip_member(archive, self.members[index])
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix="mangacrisp_thumbnail_",
                suffix=".img",
            )
            temporary_path = Path(temporary_name)
            try:
                with os.fdopen(file_descriptor, "wb") as destination, archive.open(member) as source:
                    copy_stream_limited(source, destination)
                return self._decode_image_file(temporary_path, size)
            finally:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _zip_member(archive: zipfile.ZipFile, expected: _ZipThumbnailMember) -> zipfile.ZipInfo:
        for candidate in archive.infolist():
            if candidate.filename == expected.name and candidate.header_offset == expected.header_offset:
                if (candidate.file_size, candidate.compress_size, candidate.CRC) != (
                    expected.file_size,
                    expected.compressed_size,
                    expected.crc,
                ):
                    break
                validate_archive_members(
                    [ArchiveImageMember(candidate.filename, candidate.file_size, candidate.compress_size)]
                )
                return candidate
        raise RuntimeError("archive member changed or is unavailable")

    @classmethod
    def _decode_image_file(cls, path: Path, target_size: QSize) -> QImage:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        source_size = reader.size()
        scaled_size = cls._scaled_image_size(source_size, target_size)
        reader.setScaledSize(scaled_size)
        image = reader.read()
        if image.isNull():
            raise RuntimeError("image decode failed")
        # Qt applies EXIF rotation after scaled decoding on some backends.
        # Constrain the final oriented pixels as well as the reader request.
        if image.width() > target_size.width() or image.height() > target_size.height():
            image = cls._scale(image, target_size)
        return image

    @staticmethod
    def _scaled_image_size(source_size: QSize, target_size: QSize) -> QSize:
        source_width = source_size.width()
        source_height = source_size.height()
        target_width = target_size.width()
        target_height = target_size.height()
        if min(source_width, source_height, target_width, target_height) <= 0:
            raise RuntimeError("invalid image size")
        scale = min(1.0, target_width / source_width, target_height / source_height)
        return QSize(max(1, round(source_width * scale)), max(1, round(source_height * scale)))

    def _decode_pdf(self, index: int, size: QSize) -> QImage:
        if self.pdf_path is None:
            raise RuntimeError("PDF source unavailable")
        try:
            import pypdfium2 as pdfium

            with _PDFIUM_LOCK:
                document = pdfium.PdfDocument(self.pdf_path)
                try:
                    page = document[index]
                    try:
                        bitmap = page.render(
                            scale=self._pdf_thumbnail_scale(page.get_size(), size),
                            rev_byteorder=True,
                            prefer_bgrx=True,
                        )
                        try:
                            pil_image = bitmap.to_pil().convert("RGB")
                            image = QImage(
                                pil_image.tobytes(),
                                pil_image.width,
                                pil_image.height,
                                pil_image.width * 3,
                                QImage.Format_RGB888,
                            ).copy()
                        finally:
                            bitmap.close()
                    finally:
                        page.close()
                finally:
                    document.close()
        except Exception as exc:
            raise RuntimeError(f"PDF page {index + 1} thumbnail failed") from exc
        return self._scale(image, size)

    @staticmethod
    def _pdf_thumbnail_scale(page_size: tuple[float, float], target_size: QSize) -> float:
        """Fit a PDF page to its thumbnail target without a fixed-DPI peak."""
        try:
            page_width, page_height = (float(value) for value in page_size)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("invalid PDF page size") from exc
        target_width = float(target_size.width())
        target_height = float(target_size.height())
        values = (page_width, page_height, target_width, target_height)
        if not all(isfinite(value) and value > 0 for value in values):
            raise RuntimeError("invalid PDF page size")
        scale = min(target_width / page_width, target_height / page_height)
        if not isfinite(scale) or scale <= 0:
            raise RuntimeError("invalid PDF thumbnail scale")
        return scale


class _ThumbnailSignals(QObject):
    decoded = Signal(int, int, object, object)


class _ThumbnailTask(QRunnable):
    def __init__(self, source: ThumbnailSource, index: int, generation: int, signals: _ThumbnailSignals) -> None:
        super().__init__()
        self.source = source
        self.index = index
        self.generation = generation
        self.signals = signals

    def run(self) -> None:
        try:
            image = self.source.decode(self.index)
            error = None
        except Exception as exc:  # noqa: BLE001 - one broken page must not break the overview.
            image = QImage()
            error = str(exc)
        try:
            self.signals.decoded.emit(self.generation, self.index, image, error)
        except RuntimeError:
            pass


class ThumbnailController(QObject):
    """Single-worker, generation-scoped thumbnail requests with a byte LRU."""

    thumbnail_ready = Signal(int, object, object)

    def __init__(self, pages: Sequence[Path], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.source = ThumbnailSource.from_pages(pages)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.signals = _ThumbnailSignals()
        self.signals.decoded.connect(self._on_decoded)
        self.generation = 0
        # A prior generation can still finish after ``pool.clear()``.  Keep
        # its identity so its completion cannot clear a newer same-page
        # request.
        self.pending: set[tuple[int, int]] = set()
        self.cache: OrderedDict[int, QImage] = OrderedDict()
        self.cache_bytes = 0
        self._closed = False

    def set_generation(self, generation: int) -> None:
        self.generation = generation
        self.pool.clear()
        self.pending.clear()

    def request(self, indexes: Sequence[int], generation: int) -> None:
        if self._closed or generation != self.generation:
            return
        for index in indexes:
            if index < 0 or index >= len(self.source):
                continue
            cached = self.cache.get(index)
            if cached is not None:
                self.cache.move_to_end(index)
                self.thumbnail_ready.emit(index, cached, None)
                continue
            request = (generation, index)
            if request in self.pending:
                continue
            self.pending.add(request)
            self.pool.start(_ThumbnailTask(self.source, index, generation, self.signals))

    def shutdown(self) -> None:
        """Cancel queued work and drain the one active decoder before teardown."""
        self._closed = True
        self.generation += 1
        self.pool.clear()
        self.pending.clear()
        self.pool.waitForDone()

    def _on_decoded(self, generation: int, index: int, image: QImage, error: str | None) -> None:
        self.pending.discard((generation, index))
        if self._closed or generation != self.generation:
            return
        if error is None and not image.isNull():
            self._remember(index, image)
        self.thumbnail_ready.emit(index, image, error)

    def _remember(self, index: int, image: QImage) -> None:
        previous = self.cache.pop(index, None)
        if previous is not None:
            self.cache_bytes -= previous.bytesPerLine() * previous.height()
        self.cache[index] = image
        self.cache_bytes += image.bytesPerLine() * image.height()
        while self.cache and self.cache_bytes > THUMBNAIL_CACHE_BYTES:
            _old_index, old_image = self.cache.popitem(last=False)
            self.cache_bytes -= old_image.bytesPerLine() * old_image.height()


__all__ = ["THUMBNAIL_CACHE_BYTES", "THUMBNAIL_SIZE", "ThumbnailController", "ThumbnailSource"]
