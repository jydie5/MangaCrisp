"""Lazy, direct-image page access for the narrow EPUB comic profile.

This module deliberately does not register ``.epub`` with the reader.  It is
the package-to-page boundary for a later integration: metadata is validated by
``epub_probe`` first, while image bytes remain in the archive until a caller
asks for an individual physical spine entry.
"""

from __future__ import annotations

import shutil
import tempfile
import unicodedata
import zipfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from mangacrisp_app.archive_utils import archive_member_output_path
from mangacrisp_app.epub_probe import (
    EpubMetadata,
    EpubProbeError,
    EpubSpineItem,
    inspect_epub,
)
from mangacrisp_app.page_provider import LazyZipPageList

SUPPORTED_IMAGE_MEDIA_TYPES = frozenset(
    {"image/gif", "image/jpeg", "image/png", "image/webp"}
)

_PIL_FORMAT_MEDIA_TYPES = {
    "GIF": "image/gif",
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


class EpubPageList(LazyZipPageList):
    """A lazy physical-page view of an inspected direct-image EPUB.

    ``members`` intentionally follows the linear spine, rather than archive
    order.  A repeated ``itemref`` therefore remains a repeated physical page.
    ``close()`` removes this instance's temporary extraction directory and is
    terminal: further page, stem, or cache-identity requests raise
    ``RuntimeError``.  Callers may instead remove the returned cleanup
    directory themselves, as with the existing ZIP page source.
    """

    def __init__(
        self,
        archive_path: Path,
        temp_dir: Path,
        metadata: EpubMetadata,
        members: list[zipfile.ZipInfo],
        spine: tuple[EpubSpineItem, ...],
    ) -> None:
        super().__init__(archive_path, temp_dir, members)
        self.metadata = metadata
        self.spine = spine
        self._validated_indexes: set[int] = set()
        self._closed = False

    def page_stem(self, index: int) -> str:
        """Return a display stem without extracting the page image."""
        self._require_open()
        index = self._normalize_index(index)
        output = archive_member_output_path(self.temp_dir, self.members[index].filename)
        if output is None:
            raise EpubProbeError("corrupt")
        stem = output.stem
        return stem or f"page-{index + 1:04d}"

    def materialize(self, index: int) -> Path:
        self._require_open()
        index = self._normalize_index(index)
        with self._materialize_lock:
            previously_valid = (
                index in self._validated_indexes
                and (cached := self.extracted.get(index)) is not None
                and cached.is_file()
            )
            try:
                path = super().materialize(index)
            except (
                OSError,
                RuntimeError,
                zipfile.BadZipFile,
                zipfile.LargeZipFile,
                NotImplementedError,
            ) as exc:
                self.extracted.pop(index, None)
                self._discard_member_output(index)
                raise EpubProbeError("corrupt") from exc
            if previously_valid:
                return path
            try:
                self._validate_image(path, self.spine[index].media_type)
            except EpubProbeError:
                # Do not leave a corrupt or MIME-confused file for a later
                # caller.  This is safe for a repeated itemref: the probe
                # forbids distinct manifest declarations for one resource.
                self.extracted.pop(index, None)
                self._discard_invalid_extraction(path)
                raise
            self._validated_indexes.add(index)
            return path

    def close(self) -> None:
        """Delete extracted files and permanently close this page source."""
        with self._materialize_lock:
            self.extracted.clear()
            self._validated_indexes.clear()
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self._closed = True

    def cache_source_identity(self, index: int) -> str:
        self._require_open()
        return super().cache_source_identity(index)

    def _normalize_index(self, index: int) -> int:
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        return index

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("EPUB page source is closed")

    @staticmethod
    def _validate_image(path: Path, declared_media_type: str) -> None:
        try:
            with Image.open(path) as image:
                actual_format = image.format
                image.verify()
        except Image.DecompressionBombError as exc:
            raise EpubProbeError("archive-abuse") from exc
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            raise EpubProbeError("corrupt") from exc
        if _PIL_FORMAT_MEDIA_TYPES.get(actual_format or "") != declared_media_type:
            raise EpubProbeError("corrupt")

    def _discard_invalid_extraction(self, path: Path) -> None:
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent != self.temp_dir:
            try:
                parent.rmdir()
            except OSError:
                return
            parent = parent.parent

    def _discard_member_output(self, index: int) -> None:
        output = archive_member_output_path(self.temp_dir, self.members[index].filename)
        if output is not None:
            self._discard_invalid_extraction(output)


def open_epub_image_pages(path: Path | str) -> tuple[EpubPageList, Path]:
    """Open the direct-image EPUB profile without decoding any page image.

    Only declared PNG, JPEG, GIF, and WebP linear spine resources are accepted.
    XHTML, SVG, and unknown media remain metadata-only and raise the stable
    ``unsupported`` reason here.  A package with mixed *layout* declarations
    is still accepted when every page is a supported direct image; its warning
    and layout metadata are retained for a later reader integration.  The
    returned cleanup directory is owned by the caller and may also be removed
    through terminal ``pages.close()``.
    """
    archive_path = Path(path).expanduser().resolve()
    metadata = inspect_epub(archive_path)
    spine = metadata.page_spine
    if metadata.content_profile != "direct-image-candidate" or any(
        item.media_type not in SUPPORTED_IMAGE_MEDIA_TYPES for item in spine
    ):
        raise EpubProbeError("unsupported")

    # The probe's resource paths are NFC-normalized.  Retain the original
    # ZipInfo objects so archive.open(info) reads an NFD-named ZIP member
    # correctly and does not accidentally select a name collision.
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members_by_path: dict[str, zipfile.ZipInfo] = {}
            for info in archive.infolist():
                original = getattr(info, "orig_filename", info.filename)
                normalized = unicodedata.normalize("NFC", original).rstrip("/")
                if normalized in members_by_path:
                    raise EpubProbeError("corrupt")
                members_by_path[normalized] = info
            members = []
            for item in spine:
                member = members_by_path.get(item.resource_path)
                if member is None or member.is_dir():
                    raise EpubProbeError("corrupt")
                members.append(member)
    except EpubProbeError:
        raise
    except (
        OSError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        NotImplementedError,
    ) as exc:
        raise EpubProbeError("corrupt") from exc

    temp_dir = Path(tempfile.mkdtemp(prefix="mangacrisp_epub_pages_"))
    try:
        return EpubPageList(archive_path, temp_dir, metadata, members, spine), temp_dir
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


__all__ = ["SUPPORTED_IMAGE_MEDIA_TYPES", "EpubPageList", "open_epub_image_pages"]
