from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

from mangacrisp_app.platform import capture_linux
from mangacrisp_app.platform.capture_base import (
    CaptureDisplay,
    CaptureRect,
    PermissionState,
)


def display(identifier: str = "a", x: int = 0, y: int = 0, width: int = 100, height: int = 50) -> CaptureDisplay:
    return CaptureDisplay(identifier, identifier, x, y, width, height)


def test_linux_presets_have_portal_triggers() -> None:
    triggers = [
        (capture_linux.portal_trigger(item.capture), capture_linux.portal_trigger(item.undo))
        for item in capture_linux.hotkey_presets()
    ]

    assert triggers == [
        ("ALT+c", "ALT+u"),
        ("CTRL+ALT+c", "CTRL+ALT+z"),
        ("CTRL+Return", "CTRL+Delete"),
    ]
    assert capture_linux.default_hotkey_bindings() == capture_linux.hotkey_presets()[0]


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({"XDG_SESSION_TYPE": "wayland"}, True),
        ({"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}, False),
        ({"WAYLAND_DISPLAY": "wayland-0"}, True),
        ({}, False),
    ],
)
def test_linux_session_detection(environ: dict[str, str], expected: bool) -> None:
    assert capture_linux.is_wayland_session(environ) is expected


def test_linux_region_must_stay_on_display() -> None:
    displays = [display("a"), display("b", x=100)]

    assert capture_linux.validate_region(CaptureRect("b", 110, 10, 20, 20), displays).identifier == "b"
    with pytest.raises(ValueError):
        capture_linux.validate_region(CaptureRect("a", 90, 10, 20, 20), displays)
    with pytest.raises(RuntimeError):
        capture_linux.validate_region(CaptureRect("gone", 0, 0, 20, 20), displays)


def test_linux_crop_scales_logical_region_to_physical_pixels() -> None:
    # Two 100x50 logical displays side by side, captured at 125% scaling.
    displays = [display("a"), display("b", x=100)]
    desktop = Image.new("RGB", (250, 63), "black")
    desktop.paste((255, 0, 0), (125, 0, 250, 63))

    cropped = capture_linux.crop_desktop_image(desktop, CaptureRect("b", 100, 0, 40, 20), displays)

    assert cropped.size == (50, 25)
    assert cropped.mode == "RGBA"
    assert cropped.getpixel((0, 0)) == (255, 0, 0, 255)


def test_linux_crop_handles_negative_display_origins() -> None:
    displays = [display("left", x=-100), display("main")]
    desktop = Image.new("RGB", (200, 50), "black")
    desktop.paste((0, 255, 0), (100, 0, 200, 50))

    cropped = capture_linux.crop_desktop_image(desktop, CaptureRect("main", 0, 0, 10, 10), displays)

    assert cropped.getpixel((0, 0)) == (0, 255, 0, 255)


def test_x11_capture_needs_no_permission() -> None:
    backend = capture_linux.LinuxScreenCaptureBackend(wayland=False)

    assert backend.permission_state() == PermissionState.GRANTED
    assert backend.request_permission() == PermissionState.GRANTED


def test_wayland_permission_uses_stored_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = capture_linux.LinuxScreenCaptureBackend(wayland=True)
    monkeypatch.setattr(backend, "_stored_screenshot_permission", lambda: None)
    assert backend.permission_state() == PermissionState.DENIED

    monkeypatch.setattr(backend, "_stored_screenshot_permission", lambda: "yes")
    assert backend.permission_state() == PermissionState.GRANTED


def test_wayland_permission_request_retries_immediate_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = capture_linux.LinuxScreenCaptureBackend(wayland=True)
    attempts: list[float] = []

    def screenshot(_timeout: float) -> Image.Image:
        attempts.append(_timeout)
        if len(attempts) == 1:
            raise PermissionError("denied")
        return Image.new("RGBA", (1, 1))

    monkeypatch.setattr(backend, "_portal_screenshot", screenshot)

    assert backend.request_permission() == PermissionState.GRANTED
    assert len(attempts) == 2


def test_wayland_permission_request_reports_denial(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = capture_linux.LinuxScreenCaptureBackend(wayland=True)

    def screenshot(_timeout: float) -> Image.Image:
        raise PermissionError("denied")

    monkeypatch.setattr(backend, "_portal_screenshot", screenshot)

    assert backend.request_permission() == PermissionState.DENIED


@pytest.mark.skipif(sys.platform == "win32", reason="portal URIs are POSIX file paths")
def test_wayland_screenshot_file_is_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shot = tmp_path / "Screenshot.png"
    Image.new("RGB", (4, 2), "white").save(shot)
    backend = capture_linux.LinuxScreenCaptureBackend(wayland=True)
    monkeypatch.setattr(backend, "_call_portal", lambda _function: {"uri": shot.as_uri()})

    image = backend._portal_screenshot(1)

    assert image.size == (4, 2)
    assert not shot.exists()
    assert backend.permission_state() == PermissionState.GRANTED
