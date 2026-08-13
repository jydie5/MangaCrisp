from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtTest import QTest

from mangacrisp_app.capture.coordinator import CaptureCoordinator
from mangacrisp_app.capture.session import CaptureSession
from mangacrisp_app.capture_window import CaptureWindow, capture_feedback_position
from mangacrisp_app.i18n import tr
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


def test_capture_window_saves_and_packages_with_fake_backend(
    qapp, tmp_path: Path
) -> None:
    del qapp
    backend = FakeCaptureBackend()
    played: list[bool] = []
    window = CaptureWindow(backend=backend, sound_player=lambda: played.append(True))
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
    assert played == [True]
    assert window.package_button.isEnabled()
    window.stop_capture()
    window.close()
    assert backend.unregistered


def test_capture_mode_callbacks_hide_and_restore_after_start(
    qapp, tmp_path: Path
) -> None:
    del qapp
    backend = FakeCaptureBackend()
    states: list[bool] = []
    returned: list[bool] = []
    window = CaptureWindow(
        backend=backend,
        on_capture_mode_changed=states.append,
        on_return_to_bookshelf=lambda: returned.append(True),
    )
    window.destination_edit.setText(str(tmp_path))
    window.set_region(CaptureRect("display-1", 0, 0, 320, 480))

    window.start_capture()
    for _ in range(100):
        QTest.qWait(20)
        if states:
            break
    assert states == [True]
    assert not window.package_button.isEnabled()

    window.return_to_bookshelf()
    assert states == [True, False]
    assert returned == [True]
    window.close()


def test_completed_capture_cannot_be_packaged_or_imported_twice(
    qapp, tmp_path: Path
) -> None:
    del qapp
    imported: list[Path] = []
    window = CaptureWindow(backend=FakeCaptureBackend(), on_import=imported.append)
    window.session = CaptureSession.create(tmp_path, "Completed once")
    window.session.capture(Image.new("RGB", (320, 480), (20, 80, 160)))
    window.coordinator = CaptureCoordinator(window.session)
    window.reload_pages()
    window.update_controls()

    window.package_session()
    for _ in range(100):
        QTest.qWait(20)
        if window.session.manifest.output is not None and imported:
            break

    assert len(imported) == 1
    assert window.package_button.text() == tr("完了済み")
    assert not window.package_button.isEnabled()

    window.package_session()
    QTest.qWait(100)

    assert len(imported) == 1
    assert window.status_label.text() == tr("このセッションは完了済みです。")
    window.close()


def test_capture_ui_explains_immediate_png_persistence(qapp) -> None:
    del qapp
    window = CaptureWindow(backend=FakeCaptureBackend())

    assert window.package_button.text() == tr("撮影を完了")
    assert window.import_check.text() == tr("完了後に本棚へ追加（表紙を作成）")
    assert window.return_button.text() == tr("本棚へ戻る")
    assert window.visual_feedback_check.isChecked()
    assert window.sound_check.isChecked()
    window.close()
