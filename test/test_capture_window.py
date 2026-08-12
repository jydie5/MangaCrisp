from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize

from mangacrisp_app.capture_window import CaptureWindow, capture_feedback_position
from mangacrisp_app.platform.capture_base import (
    CaptureDisplay,
    CaptureRect,
    HotkeyBinding,
    HotkeyBindings,
    PermissionState,
)


class FakeCaptureBackend:
    def __init__(self) -> None:
        self.capture_callback: Callable[[], None] | None = None
        self.undo_callback: Callable[[], None] | None = None
        self.unregistered = False
        self.opened_permission_settings = False

    def permission_state(self) -> PermissionState:
        return PermissionState.GRANTED

    def request_permission(self) -> PermissionState:
        return PermissionState.GRANTED

    def open_permission_settings(self) -> None:
        self.opened_permission_settings = True

    def list_displays(self) -> list[CaptureDisplay]:
        return [CaptureDisplay("display-1", "Test Display", 0, 0, 1920, 1080)]

    def capture_region(self, region: CaptureRect) -> Image.Image:
        return Image.new("RGB", (region.width, region.height), (20, 80, 160))

    def register_hotkeys(
        self,
        bindings: HotkeyBindings,
        on_capture: Callable[[], None],
        on_undo: Callable[[], None],
    ) -> None:
        del bindings
        self.capture_callback = on_capture
        self.undo_callback = on_undo

    def unregister_hotkeys(self) -> None:
        self.unregistered = True


def test_capture_feedback_prefers_space_above_region() -> None:
    display = CaptureDisplay("display-1", "Test Display", 0, 0, 1920, 1080)
    region = CaptureRect("display-1", 200, 200, 1200, 700)

    position = capture_feedback_position(display, region, QSize(190, 52))

    assert position is not None
    assert position.y() + 52 < region.y


def test_capture_feedback_is_omitted_when_region_fills_display() -> None:
    display = CaptureDisplay("display-1", "Test Display", 0, 0, 1920, 1080)
    region = CaptureRect("display-1", 0, 0, 1920, 1080)

    assert capture_feedback_position(display, region, QSize(190, 52)) is None


def test_capture_window_opens_screen_recording_settings(qapp) -> None:
    del qapp
    backend = FakeCaptureBackend()
    window = CaptureWindow(backend=backend)

    window.open_permission_settings()

    assert backend.opened_permission_settings
    assert "MangaCrisp" in window.status_label.text()
    window.close()


def test_capture_window_saves_and_packages_with_fake_backend(qapp, tmp_path: Path) -> None:
    del qapp
    backend = FakeCaptureBackend()
    window = CaptureWindow(backend=backend)
    window.destination_edit.setText(str(tmp_path))
    bindings = HotkeyBindings(
        HotkeyBinding(1, 1, "Test Capture"),
        HotkeyBinding(2, 1, "Test Undo"),
    )
    window.hotkey_combo.addItem("Test", bindings)
    window.hotkey_combo.setCurrentIndex(window.hotkey_combo.count() - 1)
    window.set_region(CaptureRect("display-1", 0, 0, 320, 480))

    window.start_capture()
    window.capture_requested()
    assert window.coordinator is not None
    window.coordinator.wait()
    window.signals.page_saved.emit(window.session.pages[0], None)

    assert len(window.session.pages) == 1
    assert window.page_list.count() == 1
    window.stop_capture()
    window.close()
    assert backend.unregistered
