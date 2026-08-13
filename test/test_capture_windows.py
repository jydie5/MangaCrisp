from __future__ import annotations

import ctypes
import sys

import pytest
from PIL import Image

from mangacrisp_app.platform.capture_base import CaptureRect, PermissionState

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows capture integration"
)


def test_windows_backend_lists_and_captures_display_region(qapp) -> None:
    from mangacrisp_app.platform.capture_windows import WindowsScreenCaptureBackend

    backend = WindowsScreenCaptureBackend()
    displays = backend.list_displays()

    assert backend.permission_state() == PermissionState.GRANTED
    assert backend.request_permission() == PermissionState.GRANTED
    assert displays
    display = displays[0]
    assert display.width >= 100 and display.height >= 80
    image = backend.capture_region(
        CaptureRect(display.identifier, display.x, display.y, 100, 80)
    )
    assert isinstance(image, Image.Image)
    assert image.mode == "RGBA"
    assert image.width >= 100 and image.height >= 80


def test_windows_hotkey_presets_are_distinct() -> None:
    from mangacrisp_app.platform.capture_windows import (
        MOD_ALT,
        MOD_CONTROL,
        hotkey_presets,
    )

    presets = hotkey_presets()

    assert len(presets) == 3
    assert presets[0].capture.label == "Control+Alt+C"
    assert presets[0].undo.label == "Control+Alt+Z"
    assert presets[0].capture.modifiers == MOD_CONTROL | MOD_ALT
    assert presets[0].undo.modifiers == MOD_CONTROL | MOD_ALT
    assert presets[1].capture.label == "Alt+C"
    assert presets[1].undo.label == "Alt+Z"
    for bindings in presets:
        assert (bindings.capture.key_code, bindings.capture.modifiers) != (
            bindings.undo.key_code,
            bindings.undo.modifiers,
        )


def test_windows_native_filter_dispatches_registered_hotkey(qapp) -> None:
    del qapp
    from mangacrisp_app.platform.capture_windows import (
        CAPTURE_HOTKEY_ID,
        WM_HOTKEY,
        _HotkeyEventFilter,
        _WindowsMessage,
    )

    calls: list[str] = []
    event_filter = _HotkeyEventFilter()
    event_filter.callbacks[CAPTURE_HOTKEY_ID] = lambda: calls.append("capture")
    message = _WindowsMessage()
    message.message = WM_HOTKEY
    message.wParam = CAPTURE_HOTKEY_ID

    handled, result = event_filter.nativeEventFilter(
        b"windows_generic_MSG", ctypes.addressof(message)
    )

    assert handled is True
    assert result == 0
    assert calls == ["capture"]
