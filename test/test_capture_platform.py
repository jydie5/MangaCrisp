from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

from mangacrisp_app.platform.capture_base import CaptureRect, PermissionState

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS capture integration")


def test_macos_backend_lists_and_captures_display_region(qapp, tmp_path: Path) -> None:
    from mangacrisp_app.platform.capture_macos import MacScreenCaptureBackend

    backend = MacScreenCaptureBackend()
    displays = backend.list_displays()

    assert displays
    display = displays[0]
    assert display.width >= 100 and display.height >= 100
    if backend.permission_state() != PermissionState.GRANTED:
        pytest.skip("Screen Recording permission is not granted to this test process")
    image = backend.capture_region(
        CaptureRect(display.identifier, display.x, display.y, 100, 80)
    )
    assert isinstance(image, Image.Image)
    assert image.mode == "RGBA"
    assert image.size == (100, 80)
