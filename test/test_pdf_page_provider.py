from pathlib import Path

from PIL import Image

from mangacrisp_app.page_provider import (
    PdfPageList,
    open_pages_for_viewer,
    pdf_page_count,
    prune_render_cache,
)


def make_color_pdf(path: Path, colors: list[tuple[int, int, int]]) -> None:
    pages = [Image.new("RGB", (120, 180), color) for color in colors]
    pages[0].save(path, format="PDF", save_all=True, append_images=pages[1:])


def test_pdf_pages_render_lazily_and_preserve_color(tmp_path: Path) -> None:
    source = tmp_path / "color.pdf"
    cache = tmp_path / "cache"
    make_color_pdf(source, [(230, 20, 30), (20, 210, 40), (30, 40, 220)])

    pages = PdfPageList(source, cache, dpi=96)

    assert len(pages) == 3
    assert list(cache.rglob("*.png")) == []

    rendered = pages[1]
    assert rendered.is_file()
    assert len(list(cache.rglob("*.png"))) == 1
    with Image.open(rendered) as image:
        red, green, blue = image.convert("RGB").getpixel((image.width // 2, image.height // 2))
    assert green > 180
    assert red < 80
    assert blue < 80


def test_open_pages_for_viewer_uses_pdf_page_source(tmp_path: Path) -> None:
    source = tmp_path / "book.pdf"
    make_color_pdf(source, [(255, 255, 255), (0, 0, 0)])

    pages, cleanup = open_pages_for_viewer(source)

    assert isinstance(pages, PdfPageList)
    assert len(pages) == 2
    assert cleanup is None
    assert pdf_page_count(source) == 2


def test_prune_render_cache_removes_oldest_unprotected_files(tmp_path: Path) -> None:
    old = tmp_path / "a" / "old.png"
    protected = tmp_path / "b" / "protected.png"
    newest = tmp_path / "c" / "new.png"
    for path in (old, protected, newest):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 10)
    old.touch()
    protected.touch()
    newest.touch()
    old_mtime = 1_000_000_000
    protected_mtime = old_mtime + 1
    newest_mtime = old_mtime + 2
    import os

    os.utime(old, (old_mtime, old_mtime))
    os.utime(protected, (protected_mtime, protected_mtime))
    os.utime(newest, (newest_mtime, newest_mtime))

    removed = prune_render_cache(tmp_path, max_bytes=10, protected={protected})

    assert removed == 2
    assert not old.exists()
    assert protected.exists()
    assert not newest.exists()


def test_300_page_pdf_does_not_render_until_a_page_is_requested(tmp_path: Path) -> None:
    source = tmp_path / "large.pdf"
    cache = tmp_path / "cache"
    make_color_pdf(source, [(index % 255, 80, 160) for index in range(300)])

    pages = PdfPageList(source, cache, dpi=72)

    assert len(pages) == 300
    assert list(cache.rglob("*.png")) == []
    assert pages[0].is_file()
    assert pages[150].is_file()
    assert pages[299].is_file()
    assert len(list(cache.rglob("*.png"))) == 3
