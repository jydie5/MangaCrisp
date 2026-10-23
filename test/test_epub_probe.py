from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mangacrisp_app.epub_probe import EpubProbeError, inspect_epub


def _epub(path: Path, *, version: str = "3.0", direction: str = "rtl", extra: dict[str, bytes] | None = None, opf: str | None = None) -> Path:
    package = opf or f'''<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="{version}"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Test comic</dc:title><dc:creator>Ada</dc:creator><dc:language>ja</dc:language><meta property="rendition:layout">pre-paginated</meta>
</metadata><manifest><item id="cover" href="Images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>
<item id="two" href="Images/two.jpg" media-type="image/jpeg"/><item id="one" href="Images/one.jpg" media-type="image/jpeg"/>
<item id="aux" href="Images/aux.jpg" media-type="image/jpeg"/></manifest>
<spine page-progression-direction="{direction}"><itemref idref="one" properties="page-spread-right"/><itemref idref="aux" linear="no"/><itemref idref="two" properties="page-spread-left"/></spine></package>'''
    entries = {
        "mimetype": b"application/epub+zip",
        "META-INF/container.xml": b'<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
        "OPS/book.opf": package.encode(),
        "OPS/Images/cover.jpg": b"cover",
        "OPS/Images/one.jpg": b"one",
        "OPS/Images/two.jpg": b"two",
        "OPS/Images/aux.jpg": b"aux",
    }
    entries.update(extra or {})
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", entries.pop("mimetype"), compress_type=zipfile.ZIP_STORED)
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def test_inspect_epub_uses_spine_order_and_keeps_auxiliary_metadata(tmp_path: Path) -> None:
    metadata = inspect_epub(_epub(tmp_path / "comic.epub"))
    assert metadata.title == "Test comic"
    assert metadata.creators == ("Ada",)
    assert metadata.direction == "rtl"
    assert metadata.layout == "fixed"
    assert metadata.cover_path == "OPS/Images/cover.jpg"
    assert [item.id for item in metadata.manifest] == ["cover", "two", "one", "aux"]
    assert metadata.content_profile == "direct-image-candidate"
    assert [item.idref for item in metadata.spine] == ["one", "aux", "two"]
    assert [item.idref for item in metadata.page_spine] == ["one", "two"]
    assert metadata.auxiliary_spine[0].idref == "aux"
    assert [item.spread_position for item in metadata.page_spine] == ["right", "left"]


def test_epub_keeps_global_and_per_spine_layouts_and_rendition_spread_aliases(tmp_path: Path) -> None:
    opf = '''<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Overrides</dc:title><meta property="rendition:layout" refines="#item">pre-paginated</meta></metadata><manifest>
<item id="one" href="Images/one.jpg" media-type="image/jpeg"/><item id="two" href="Images/two.jpg" media-type="image/jpeg"/></manifest>
<spine><itemref idref="one" properties="rendition:layout-pre-paginated rendition:page-spread-center"/>
<itemref idref="two" properties="rendition:layout-reflowable rendition:page-spread-left page-spread-right"/></spine></package>'''
    metadata = inspect_epub(_epub(tmp_path / "overrides.epub", opf=opf))
    assert metadata.global_layout == "reflowable"
    assert metadata.effective_layout == "mixed"
    assert [item.effective_layout for item in metadata.page_spine] == ["fixed", "reflowable"]
    assert metadata.page_spine[0].spread_position == "center"
    assert metadata.page_spine[1].spread_position == "unspecified"
    assert {"mixed-layout", "conflicting-spread"}.issubset(metadata.warnings)


def test_epub2_legacy_cover_relative_parent_and_unknown_media_are_metadata(tmp_path: Path) -> None:
    opf = '''<package xmlns="http://www.idpf.org/2007/opf" version="2.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:title>Legacy</dc:title><meta name="cover" content="cover"/></metadata><manifest>
<item id="cover" href="../Images/cover.jpg" media-type="image/jpeg"/><item id="page" href="../Images/one.jpg" media-type="application/x-private"/></manifest><spine><itemref idref="page"/></spine></package>'''
    metadata = inspect_epub(
        _epub(
            tmp_path / "legacy.epub",
            version="2.0",
            direction="default",
            opf=opf,
            extra={"Images/cover.jpg": b"cover", "Images/one.jpg": b"one"},
        )
    )
    assert metadata.cover_path == "Images/cover.jpg"
    assert metadata.direction == "unknown"
    assert {"reflowable", "unknown-media-type"}.issubset(metadata.warnings)


def test_epub_with_only_auxiliary_spine_items_is_corrupt(tmp_path: Path) -> None:
    opf = '''<package><metadata/><manifest><item id="x" href="Images/one.jpg" media-type="image/jpeg"/></manifest>
<spine><itemref idref="x" linear="no"/></spine></package>'''
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(_epub(tmp_path / "auxiliary.epub", opf=opf))
    assert error.value.reason == "corrupt"


@pytest.mark.parametrize("payload", [b'<!DOCTYPE x [<!ENTITY x "y">]><x>&x;</x>', '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x><x/>'.encode("utf-16")])
def test_epub_rejects_doctype_and_entities_in_utf8_or_utf16(tmp_path: Path, payload: bytes) -> None:
    path = _epub(tmp_path / "unsafe.epub", extra={"META-INF/container.xml": payload})
    with pytest.raises(EpubProbeError, match="corrupt"):
        inspect_epub(path)


@pytest.mark.parametrize(
    ("opf", "reason"),
    [
        ('<manifest/><spine><itemref idref="missing"/></spine>', "corrupt"),
        ('<manifest><item id="x" href="https://x/p.jpg" media-type="image/jpeg"/></manifest><spine><itemref idref="x"/></spine>', "unsupported"),
        ('<manifest><item id="x" href="%2e%2e/%2e%2e/p.jpg" media-type="image/jpeg"/></manifest><spine><itemref idref="x"/></spine>', "archive-abuse"),
    ],
)
def test_epub_rejects_bad_spine_and_external_or_escaping_uris(tmp_path: Path, opf: str, reason: str) -> None:
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(
            _epub(
                tmp_path / "bad.epub",
                opf=(
                    '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
                    '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Bad</dc:title></metadata>'
                    f"{opf}</package>"
                ),
            )
        )
    assert error.value.reason == reason


def test_epub_resolves_percent_escaped_hash_as_an_in_package_resource(tmp_path: Path) -> None:
    opf = '''<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Hash</dc:title></metadata>
<manifest><item id="page" href="Images/page%231.jpg" media-type="image/jpeg"/></manifest><spine><itemref idref="page"/></spine></package>'''
    metadata = inspect_epub(
        _epub(tmp_path / "hash.epub", opf=opf, extra={"OPS/Images/page#1.jpg": b"page"})
    )
    assert metadata.page_spine[0].resource_path == "OPS/Images/page#1.jpg"


def test_epub_rejects_bad_mimetype_duplicate_paths_and_encryption(tmp_path: Path) -> None:
    bad_mimetype = tmp_path / "bad-mimetype.epub"
    _epub(bad_mimetype)
    with zipfile.ZipFile(bad_mimetype, "a") as archive, pytest.warns(UserWarning, match="Duplicate name"):
        archive.writestr("mimetype", b"application/epub+zip")
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(bad_mimetype)
    assert error.value.reason == "archive-abuse"

    protected = _epub(tmp_path / "protected.epub", extra={"META-INF/encryption.xml": b"<encryption/>"})
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(protected)
    assert error.value.reason == "protected"


def test_epub_rejects_malformed_xml_symlink_and_archive_limits(tmp_path: Path, monkeypatch) -> None:
    malformed = _epub(tmp_path / "malformed.epub", extra={"META-INF/container.xml": b"<container>"})
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(malformed)
    assert error.value.reason == "corrupt"

    symlink = _epub(tmp_path / "symlink.epub")
    with zipfile.ZipFile(symlink, "a") as archive:
        info = zipfile.ZipInfo("OPS/link")
        info.external_attr = 0o120777 << 16
        archive.writestr(info, b"target")
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(symlink)
    assert error.value.reason == "archive-abuse"

    monkeypatch.setattr("mangacrisp_app.epub_probe.MAX_MEMBERS", 1)
    with pytest.raises(EpubProbeError) as error:
        inspect_epub(_epub(tmp_path / "limit.epub"))
    assert error.value.reason == "archive-abuse"
