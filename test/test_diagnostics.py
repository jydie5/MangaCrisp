from pathlib import Path

from mangacrisp_app.diagnostics import (
    app_version,
    diagnostics_text,
    directory_size,
    module_version,
)


def test_diagnostics_omit_cache_path_and_user_content(tmp_path: Path) -> None:
    private_name = "private-book-title"
    cache_file = tmp_path / private_name / "page.png"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_bytes(b"12345")

    text = diagnostics_text(book_count=3, cache_dir=tmp_path)

    assert "bookshelf_items: 3" in text
    assert "cache_bytes: 5" in text
    assert str(tmp_path) not in text
    assert private_name not in text
    assert directory_size(tmp_path) == 5
    assert app_version() != "not installed"
    assert module_version("PIL") != "not installed"
    assert module_version("pypdfium2", "PYPDFIUM_INFO") != "not installed"
