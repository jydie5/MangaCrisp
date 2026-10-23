from __future__ import annotations

import struct
import zipfile
import zlib
from pathlib import Path

import pytest

from mangacrisp_app.epub_probe import EpubProbeError, inspect_epub

MIMETYPE = b"application/epub+zip"
CONTAINER = (
    b'<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
    b"<rootfiles><rootfile full-path=\"OPS/book.opf\" "
    b'media-type="application/oebps-package+xml"/></rootfiles></container>'
)


def _raw_zip(path: Path, entries: list[tuple[bytes, bytes, int, int]]) -> Path:
    """Write a minimal ZIP without ZipFile's filename sanitization."""
    local_entries: list[bytes] = []
    central_entries: list[bytes] = []
    offset = 0
    for name, data, compression, flags in entries:
        checksum = zlib.crc32(data) & 0xFFFFFFFF
        local = struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50,
            20,
            flags,
            compression,
            0,
            0,
            checksum,
            len(data),
            len(data),
            len(name),
            0,
        ) + name + data
        central = struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50,
            20,
            20,
            flags,
            compression,
            0,
            0,
            checksum,
            len(data),
            len(data),
            len(name),
            0,
            0,
            0,
            0,
            0,
            offset,
        ) + name
        local_entries.append(local)
        central_entries.append(central)
        offset += len(local)
    body = b"".join(local_entries)
    directory = b"".join(central_entries)
    path.write_bytes(
        body
        + directory
        + struct.pack(
            "<IHHHHIIH",
            0x06054B50,
            0,
            0,
            len(entries),
            len(entries),
            len(directory),
            len(body),
            0,
        )
    )
    return path


def _opf(*, href: str = "page.jpg", metadata: str = "", item_type: str = "image/jpeg") -> str:
    return f'''<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{metadata}</metadata>
    <manifest><item id="page" href="{href}" media-type="{item_type}"/></manifest>
    <spine><itemref idref="page"/></spine></package>'''


def _write_epub(path: Path, opf: str, resources: dict[str, bytes] | None = None) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", MIMETYPE, compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", CONTAINER)
        archive.writestr("OPS/book.opf", opf)
        for name, data in (resources or {"OPS/page.jpg": b"page"}).items():
            archive.writestr(name, data)
    return path


@pytest.mark.parametrize(
    "bad_name",
    [b"mimetype\x00suffix", b"OPS/./book.opf", b"OPS//book.opf"],
)
def test_rejects_raw_nul_and_noncanonical_zip_member_names(tmp_path: Path, bad_name: bytes) -> None:
    entries = [
        (b"mimetype", MIMETYPE, zipfile.ZIP_STORED, 0),
        (b"META-INF/container.xml", CONTAINER, zipfile.ZIP_STORED, 0),
        (b"OPS/book.opf", _opf().encode(), zipfile.ZIP_STORED, 0),
        (b"OPS/page.jpg", b"page", zipfile.ZIP_STORED, 0),
    ]
    if bad_name.startswith(b"mimetype"):
        entries[0] = (bad_name, MIMETYPE, zipfile.ZIP_STORED, 0)
    else:
        entries[2] = (bad_name, _opf().encode(), zipfile.ZIP_STORED, 0)

    with pytest.raises(EpubProbeError) as error:
        inspect_epub(_raw_zip(tmp_path / "unsafe-name.epub", entries))
    assert error.value.reason == "archive-abuse"


def test_reports_unsupported_for_a_zip_compression_method_it_cannot_read(tmp_path: Path) -> None:
    path = _raw_zip(
        tmp_path / "unsupported-compression.epub",
        [
            (b"mimetype", MIMETYPE, zipfile.ZIP_STORED, 0),
            (b"META-INF/container.xml", CONTAINER, 99, 0),
        ],
    )

    with pytest.raises(EpubProbeError) as error:
        inspect_epub(path)
    assert error.value.reason == "unsupported"


def test_rejects_oversized_mimetype_before_opening_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _raw_zip(
        tmp_path / "oversized-mimetype.epub",
        [(b"mimetype", b"x" * (1024 * 1024), zipfile.ZIP_STORED, 0)],
    )
    original_open = zipfile.ZipFile.open

    def forbid_mimetype_open(self: zipfile.ZipFile, name, *args, **kwargs):
        info = name if isinstance(name, zipfile.ZipInfo) else self.getinfo(name)
        if info.filename == "mimetype":
            raise AssertionError("oversized mimetype must be rejected before reading")
        return original_open(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", forbid_mimetype_open)
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(path)
    assert error.value.reason == "corrupt"


def test_normalizes_a_utf8_flagged_nfd_manifest_href(tmp_path: Path) -> None:
    path = _write_epub(
        tmp_path / "nfd.epub",
        _opf(href="cafe&#769;.jpg"),
        {"OPS/cafe\u0301.jpg": b"page"},
    )

    metadata = inspect_epub(path)
    assert metadata.page_spine[0].resource_path == "OPS/caf\u00e9.jpg"


def test_rejects_foreign_opf_namespace_and_ignores_foreign_dc_metadata(tmp_path: Path) -> None:
    foreign_opf = '''<wrong:package xmlns:wrong="urn:not-opf"><wrong:metadata/>
    <wrong:manifest/><wrong:spine/></wrong:package>'''
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(_write_epub(tmp_path / "foreign-opf.epub", foreign_opf))
    assert error.value.reason == "corrupt"

    metadata = inspect_epub(
        _write_epub(
            tmp_path / "foreign-dc.epub",
            _opf(metadata='<bad:title xmlns:bad="urn:not-dc">Spoofed title</bad:title>'),
        )
    )
    assert metadata.title == "foreign-dc"


@pytest.mark.parametrize(
    ("href", "reason"),
    [
        ("https://example.invalid/page.jpg", "unsupported"),
        ("../../outside.jpg", "archive-abuse"),
    ],
)
def test_namespaced_manifest_uri_rejections_reach_uri_validation(tmp_path: Path, href: str, reason: str) -> None:
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(_write_epub(tmp_path / "bad-uri.epub", _opf(href=href)))
    assert error.value.reason == reason
