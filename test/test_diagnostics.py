import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from mangacrisp_app.diagnostics import (
    app_version,
    diagnostics_text,
    directory_size,
    module_version,
    vulkan_loader_status,
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


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux reports the system Vulkan loader")
def test_linux_diagnostics_report_vulkan_loader(tmp_path: Path) -> None:
    with patch("mangacrisp_app.diagnostics.ctypes.util.find_library", return_value=None):
        assert vulkan_loader_status() == "missing (install libvulkan1)"
        assert "vulkan_loader: missing" in diagnostics_text(book_count=0, cache_dir=tmp_path)
    with patch("mangacrisp_app.diagnostics.ctypes.util.find_library", return_value="libvulkan.so.1"):
        assert "vulkan_loader: found" in diagnostics_text(book_count=0, cache_dir=tmp_path)
