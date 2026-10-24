"""Pure-Python, metadata-only inspection for untrusted EPUB packages."""

from __future__ import annotations

import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
from xml.parsers import expat

MAX_MEMBERS = 20_000
MAX_SINGLE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024 * 1024
MAX_RATIO = 1_000
MAX_XML_BYTES = 2 * 1024 * 1024
MIMETYPE = b"application/epub+zip"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
OPF_MEDIA_TYPE = "application/oebps-package+xml"


class EpubProbeError(RuntimeError):
    """A stable, non-user-supplied reason for a rejected EPUB."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class EpubSpineItem:
    idref: str
    resource_path: str
    media_type: str
    linear: bool
    spread_position: str
    effective_layout: str


@dataclass(frozen=True)
class EpubManifestItem:
    id: str
    resource_path: str
    media_type: str
    properties: tuple[str, ...]


@dataclass(frozen=True)
class EpubMetadata:
    title: str
    creators: tuple[str, ...]
    language: str | None
    version: str
    package_path: str
    global_layout: str
    effective_layout: str
    direction: str
    cover_path: str | None
    warnings: tuple[str, ...]
    manifest: tuple[EpubManifestItem, ...]
    spine: tuple[EpubSpineItem, ...]

    @property
    def layout(self) -> str:
        """Short alias for the package-level rendition declaration."""
        return self.global_layout

    @property
    def page_spine(self) -> tuple[EpubSpineItem, ...]:
        return tuple(item for item in self.spine if item.linear)

    @property
    def auxiliary_spine(self) -> tuple[EpubSpineItem, ...]:
        return tuple(item for item in self.spine if not item.linear)

    @property
    def content_profile(self) -> str:
        """A structural hint only; it does not claim rendering support."""
        direct_images = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        return "direct-image-candidate" if all(item.media_type in direct_images for item in self.page_spine) else "unverified"


def inspect_epub(path: Path | str) -> EpubMetadata:
    """Inspect OCF/OPF structure without decoding, extracting, or rendering pages."""
    source = Path(path)
    try:
        with zipfile.ZipFile(source) as archive:
            members = _validate_archive(archive)
            _validate_mimetype(archive, members)
            if "META-INF/encryption.xml" in members:
                raise EpubProbeError("protected")
            container = _safe_xml(_read_member(archive, members, "META-INF/container.xml"))
            package_path = _container_package_path(container, members)
            package = _safe_xml(_read_member(archive, members, package_path))
            return _inspect_package(package, package_path, members, source.stem)
    except EpubProbeError:
        raise
    except NotImplementedError as exc:
        raise EpubProbeError("unsupported") from exc
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise EpubProbeError("corrupt") from exc


def _validate_archive(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        raise EpubProbeError("archive-abuse")
    total = 0
    result: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        name = _safe_member_name(getattr(info, "orig_filename", info.filename), directory=info.is_dir())
        if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise EpubProbeError("unsupported")
        if info.flag_bits & 1 or _is_symlink(info):
            raise EpubProbeError("protected" if info.flag_bits & 1 else "archive-abuse")
        if info.file_size < 0 or info.file_size > MAX_SINGLE_BYTES:
            raise EpubProbeError("archive-abuse")
        total += info.file_size
        if total > MAX_TOTAL_BYTES or (info.file_size and (info.compress_size <= 0 or info.file_size / info.compress_size > MAX_RATIO)):
            raise EpubProbeError("archive-abuse")
        if name in result:
            raise EpubProbeError("archive-abuse")
        result[name] = info
    return result


def _safe_member_name(name: str, *, directory: bool) -> str:
    if not name or "\\" in name or any(ord(char) < 32 for char in name):
        raise EpubProbeError("archive-abuse")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise EpubProbeError("archive-abuse")
    raw_parts = name.split("/")
    if directory and raw_parts[-1] == "":
        raw_parts.pop()
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise EpubProbeError("archive-abuse")
    normalized = unicodedata.normalize("NFC", name)
    return "/".join(normalized.rstrip("/").split("/"))


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000


def _validate_mimetype(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo]) -> None:
    infos = archive.infolist()
    info = members.get("mimetype")
    if info is None or not infos or infos[0] is not info or info.compress_type != zipfile.ZIP_STORED:
        raise EpubProbeError("corrupt")
    if info.file_size != len(MIMETYPE):
        raise EpubProbeError("corrupt")
    with archive.open(info) as stream:
        if stream.read(len(MIMETYPE) + 1) != MIMETYPE:
            raise EpubProbeError("corrupt")


def _read_member(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo], path: str) -> bytes:
    info = members.get(path)
    if info is None or info.file_size > MAX_XML_BYTES:
        raise EpubProbeError("corrupt" if info is None else "archive-abuse")
    with archive.open(info) as stream:
        data = stream.read(MAX_XML_BYTES + 1)
    if len(data) > MAX_XML_BYTES:
        raise EpubProbeError("archive-abuse")
    return data


def _safe_xml(data: bytes) -> ET.Element:
    parser = expat.ParserCreate()
    def reject(*_args):
        raise EpubProbeError("corrupt")
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    try:
        parser.Parse(data, True)
        return ET.fromstring(data)
    except EpubProbeError:
        raise
    except (ET.ParseError, expat.ExpatError, UnicodeError) as exc:
        raise EpubProbeError("corrupt") from exc


def _container_package_path(root: ET.Element, members: dict[str, zipfile.ZipInfo]) -> str:
    if root.tag != f"{{{CONTAINER_NS}}}container":
        raise EpubProbeError("corrupt")
    rootfiles = [node for node in root.iter(f"{{{CONTAINER_NS}}}rootfile") if node.get("media-type") == OPF_MEDIA_TYPE]
    if not rootfiles:
        raise EpubProbeError("corrupt")
    return _resolve_uri("", rootfiles[0].get("full-path", ""), members)


def _resolve_uri(package_path: str, value: str, members: dict[str, zipfile.ZipInfo]) -> str:
    if not value or "\\" in value or "\x00" in value or any(ord(char) < 32 for char in value):
        raise EpubProbeError("corrupt")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        raise EpubProbeError("unsupported")
    if parsed.query or parsed.fragment:
        raise EpubProbeError("corrupt")
    try:
        decoded = unicodedata.normalize("NFC", unquote(parsed.path, encoding="utf-8", errors="strict"))
    except UnicodeError as exc:
        raise EpubProbeError("corrupt") from exc
    if not decoded or "\\" in decoded or "\x00" in decoded or any(ord(char) < 32 for char in decoded):
        raise EpubProbeError("corrupt")
    if decoded.startswith("/") or re.match(r"^[A-Za-z]:", decoded):
        raise EpubProbeError("corrupt")
    stack = list(PurePosixPath(package_path).parent.parts) if package_path else []
    for part in PurePosixPath(decoded).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not stack:
                raise EpubProbeError("archive-abuse")
            stack.pop()
        else:
            stack.append(part)
    result = "/".join(stack)
    if result not in members:
        raise EpubProbeError("corrupt")
    return result


def _inspect_package(
    package: ET.Element,
    package_path: str,
    members: dict[str, zipfile.ZipInfo],
    title_fallback: str,
) -> EpubMetadata:
    if package.tag != f"{{{OPF_NS}}}package":
        raise EpubProbeError("corrupt")
    manifest_node = package.find(f"{{{OPF_NS}}}manifest")
    spine_node = package.find(f"{{{OPF_NS}}}spine")
    if manifest_node is None or spine_node is None:
        raise EpubProbeError("corrupt")
    manifest: dict[str, EpubManifestItem] = {}
    seen_paths: set[str] = set()
    for item in manifest_node:
        if item.tag != f"{{{OPF_NS}}}item":
            continue
        item_id, href, media_type = item.get("id", ""), item.get("href", ""), item.get("media-type", "")
        if not item_id or item_id in manifest or not href or not media_type:
            raise EpubProbeError("corrupt")
        resource_path = _resolve_uri(package_path, href, members)
        if resource_path in seen_paths:
            raise EpubProbeError("corrupt")
        seen_paths.add(resource_path)
        manifest[item_id] = EpubManifestItem(item_id, resource_path, media_type, tuple(sorted(item.get("properties", "").split())))
    spine: list[EpubSpineItem] = []
    conflicting_spread = False
    conflicting_layout = False
    for itemref in spine_node:
        if itemref.tag != f"{{{OPF_NS}}}itemref":
            continue
        idref = itemref.get("idref", "")
        if idref not in manifest:
            raise EpubProbeError("corrupt")
        manifest_item = manifest[idref]
        linear = itemref.get("linear", "yes").lower() != "no"
        props = set(itemref.get("properties", "").split())
        spread_values = [value for value in ("left", "right", "center") if {f"page-spread-{value}", f"rendition:page-spread-{value}"} & props]
        spread = spread_values[0] if len(spread_values) == 1 else "unspecified"
        conflicting_spread |= len(spread_values) > 1
        layout_values = [value for value in ("fixed", "reflowable") if f"rendition:layout-{'pre-paginated' if value == 'fixed' else value}" in props]
        conflicting_layout |= len(layout_values) > 1
        override = layout_values[0] if len(layout_values) == 1 else None
        spine.append(EpubSpineItem(idref, manifest_item.resource_path, manifest_item.media_type, linear, spread, override or ""))
    if not spine or not any(item.linear for item in spine):
        raise EpubProbeError("corrupt")
    metadata = package.find(f"{{{OPF_NS}}}metadata")
    title = _dc_text(metadata, "title")
    creators = _dc_texts(metadata, "creator")
    language = _dc_text(metadata, "language")
    warnings: list[str] = []
    layout = "reflowable"
    legacy_cover = None
    if metadata is not None:
        for node in metadata.findall(f"{{{OPF_NS}}}meta"):
            if node.get("property") == "rendition:layout" and not node.get("refines") and (node.text or "").strip() == "pre-paginated":
                layout = "fixed"
            if node.get("name") == "cover":
                legacy_cover = node.get("content")
    cover_ids = [item_id for item_id, item in manifest.items() if "cover-image" in item.properties]
    cover_id = cover_ids[0] if len(cover_ids) == 1 else legacy_cover
    if len(cover_ids) > 1 or (cover_ids and legacy_cover and legacy_cover != cover_ids[0]):
        warnings.append("ambiguous-cover")
    cover_path = manifest[cover_id].resource_path if cover_id in manifest else None
    if cover_id and cover_path is None:
        warnings.append("missing-cover")
    known_types = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml", "application/xhtml+xml"}
    effective_spine = tuple(
        EpubSpineItem(item.idref, item.resource_path, item.media_type, item.linear, item.spread_position, item.effective_layout or layout)
        for item in spine
    )
    effective_layouts = {item.effective_layout for item in effective_spine if item.linear}
    effective_layout = next(iter(effective_layouts)) if len(effective_layouts) == 1 else "mixed"
    if effective_layout == "mixed":
        warnings.append("mixed-layout")
    if effective_layout == "reflowable":
        warnings.append("reflowable")
    if any(item.media_type not in known_types for item in effective_spine if item.linear):
        warnings.append("unknown-media-type")
    if conflicting_spread:
        warnings.append("conflicting-spread")
    if conflicting_layout:
        warnings.append("conflicting-layout")
    direction = spine_node.get("page-progression-direction", "unknown").lower()
    direction = direction if direction in {"ltr", "rtl"} else "unknown"
    return EpubMetadata(
        title or title_fallback,
        creators,
        language,
        package.get("version", ""),
        package_path,
        layout,
        effective_layout,
        direction,
        cover_path,
        tuple(dict.fromkeys(warnings)),
        tuple(manifest.values()),
        effective_spine,
    )


def _dc_texts(metadata: ET.Element | None, name: str) -> tuple[str, ...]:
    if metadata is None:
        return ()
    return tuple(node.text.strip() for node in metadata.findall(f"{{{DC_NS}}}{name}") if node.text and node.text.strip())


def _dc_text(metadata: ET.Element | None, name: str) -> str | None:
    return next(iter(_dc_texts(metadata, name)), None)


__all__ = ["EpubManifestItem", "EpubMetadata", "EpubProbeError", "EpubSpineItem", "inspect_epub"]
