from __future__ import annotations

import ctypes
import os
from collections.abc import Callable
from contextlib import suppress
from ctypes import wintypes

from PIL import Image
from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication
from PySide6.QtGui import QGuiApplication, QImage

from mangacrisp_app.platform.capture_base import (
    CaptureDisplay,
    CaptureRect,
    HotkeyBinding,
    HotkeyBindings,
    PermissionState,
)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

VK_C = 0x43
VK_Z = 0x5A
VK_RETURN = 0x0D
VK_DELETE = 0x2E

WM_HOTKEY = 0x0312
CAPTURE_HOTKEY_ID = 0x4D43
UNDO_HOTKEY_ID = 0x4D44


class _WindowsMessage(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("lPrivate", wintypes.DWORD),
    ]


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self) -> None:
        super().__init__()
        self.callbacks: dict[int, Callable[[], None]] = {}

    def nativeEventFilter(self, _event_type, message):
        native_message = ctypes.cast(
            int(message), ctypes.POINTER(_WindowsMessage)
        ).contents
        if native_message.message != WM_HOTKEY:
            return False, 0
        callback = self.callbacks.get(int(native_message.wParam))
        if callback is None:
            return False, 0
        callback()
        return True, 0


def default_hotkey_bindings() -> HotkeyBindings:
    return HotkeyBindings(
        capture=HotkeyBinding(VK_C, MOD_CONTROL | MOD_ALT, "Control+Alt+C"),
        undo=HotkeyBinding(VK_Z, MOD_CONTROL | MOD_ALT, "Control+Alt+Z"),
    )


def hotkey_presets() -> list[HotkeyBindings]:
    return [
        default_hotkey_bindings(),
        HotkeyBindings(
            capture=HotkeyBinding(VK_C, MOD_ALT, "Alt+C"),
            undo=HotkeyBinding(VK_Z, MOD_ALT, "Alt+Z"),
        ),
        HotkeyBindings(
            capture=HotkeyBinding(VK_RETURN, MOD_CONTROL, "Control+Return"),
            undo=HotkeyBinding(VK_DELETE, MOD_CONTROL, "Control+Delete"),
        ),
    ]


class WindowsScreenCaptureBackend:
    def __init__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("Windows screen capture APIs are unavailable")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._configure_functions()
        self._event_filter = _HotkeyEventFilter()
        self._registered_ids: list[int] = []

    def _configure_functions(self) -> None:
        self._user32.RegisterHotKey.argtypes = [
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        ]
        self._user32.RegisterHotKey.restype = wintypes.BOOL
        self._user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        self._user32.UnregisterHotKey.restype = wintypes.BOOL

    def permission_state(self) -> PermissionState:
        return PermissionState.GRANTED

    def request_permission(self) -> PermissionState:
        return PermissionState.GRANTED

    def open_permission_settings(self) -> None:
        # Desktop screen capture through QScreen does not require a Windows
        # privacy grant. Keep the protocol method as an intentional no-op.
        return None

    def list_displays(self) -> list[CaptureDisplay]:
        displays: list[CaptureDisplay] = []
        for index, screen in enumerate(QGuiApplication.screens()):
            geometry = screen.geometry()
            displays.append(
                CaptureDisplay(
                    identifier=f"qt-screen-{index}:{screen.name()}",
                    name=screen.name() or f"Display {index + 1}",
                    x=geometry.x(),
                    y=geometry.y(),
                    width=geometry.width(),
                    height=geometry.height(),
                    scale=float(screen.devicePixelRatio()),
                )
            )
        return displays

    def capture_region(self, region: CaptureRect) -> Image.Image:
        display, screen = self._display_and_screen(region.display_id)
        local_x = region.x - display.x
        local_y = region.y - display.y
        if (
            not region.is_valid()
            or local_x < 0
            or local_y < 0
            or local_x + region.width > display.width
            or local_y + region.height > display.height
        ):
            raise ValueError("capture region is outside the selected display")
        pixmap = screen.grabWindow(0, local_x, local_y, region.width, region.height)
        if pixmap.isNull():
            raise RuntimeError("Windows returned an empty screen capture")
        qimage = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
        rgba = bytes(qimage.bits())
        image = Image.frombuffer(
            "RGBA",
            (qimage.width(), qimage.height()),
            rgba,
            "raw",
            "RGBA",
            qimage.bytesPerLine(),
            1,
        ).copy()
        if image.width < region.width or image.height < region.height:
            raise RuntimeError(
                "captured image dimensions are smaller than the selected region"
            )
        return image

    def register_hotkeys(
        self,
        bindings: HotkeyBindings,
        on_capture: Callable[[], None],
        on_undo: Callable[[], None],
    ) -> None:
        self.unregister_hotkeys()
        application = QCoreApplication.instance()
        if application is None:
            raise RuntimeError("a Qt application is required for Windows hotkeys")
        application.installNativeEventFilter(self._event_filter)
        self._event_filter.callbacks = {
            CAPTURE_HOTKEY_ID: on_capture,
            UNDO_HOTKEY_ID: on_undo,
        }
        try:
            for identifier, binding in (
                (CAPTURE_HOTKEY_ID, bindings.capture),
                (UNDO_HOTKEY_ID, bindings.undo),
            ):
                registered = self._user32.RegisterHotKey(
                    None,
                    identifier,
                    binding.modifiers | MOD_NOREPEAT,
                    binding.key_code,
                )
                if not registered:
                    error = ctypes.get_last_error()
                    detail = (
                        ctypes.FormatError(error).strip() if error else "unknown error"
                    )
                    raise RuntimeError(
                        f"hotkey {binding.label} is unavailable ({error}: {detail})"
                    )
                self._registered_ids.append(identifier)
        except Exception:
            self.unregister_hotkeys()
            raise

    def unregister_hotkeys(self) -> None:
        for identifier in self._registered_ids:
            self._user32.UnregisterHotKey(None, identifier)
        self._registered_ids.clear()
        application = QCoreApplication.instance()
        if application is not None:
            application.removeNativeEventFilter(self._event_filter)
        self._event_filter.callbacks.clear()

    def _display_and_screen(self, identifier: str):
        displays = self.list_displays()
        screens = QGuiApplication.screens()
        for display, screen in zip(displays, screens, strict=True):
            if display.identifier == identifier:
                return display, screen
        raise RuntimeError("selected display is no longer available")

    def __del__(self) -> None:
        with suppress(Exception):
            self.unregister_hotkeys()
