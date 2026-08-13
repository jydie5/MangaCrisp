from __future__ import annotations

import ctypes
import subprocess
from collections.abc import Callable
from contextlib import suppress
from ctypes.util import find_library

from PIL import Image
from PySide6.QtGui import QGuiApplication, QImage

from mangacrisp_app.platform.capture_base import (
    CaptureDisplay,
    CaptureRect,
    HotkeyBinding,
    HotkeyBindings,
    PermissionState,
)

CARBON_CMD = 1 << 8
CARBON_SHIFT = 1 << 9
CARBON_OPTION = 1 << 11
CARBON_CONTROL = 1 << 12

MAC_KEY_CODES = {
    "A": 0,
    "C": 8,
    "RETURN": 36,
    "DELETE": 51,
    "S": 1,
    "Z": 6,
}

K_EVENT_CLASS_KEYBOARD = int.from_bytes(b"keyb", "big")
K_EVENT_HOTKEY_PRESSED = 5
K_EVENT_PARAM_DIRECT_OBJECT = int.from_bytes(b"----", "big")
TYPE_EVENT_HOTKEY_ID = int.from_bytes(b"hkid", "big")
HOTKEY_SIGNATURE = int.from_bytes(b"MGCP", "big")
EVENT_NOT_HANDLED = -9874


class EventTypeSpec(ctypes.Structure):
    _fields_ = [("event_class", ctypes.c_uint32), ("event_kind", ctypes.c_uint32)]


class EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("identifier", ctypes.c_uint32)]


EventHandlerProc = ctypes.CFUNCTYPE(
    ctypes.c_int32,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
)


def default_hotkey_bindings() -> HotkeyBindings:
    return HotkeyBindings(
        capture=HotkeyBinding(
            key_code=MAC_KEY_CODES["C"],
            modifiers=CARBON_OPTION,
            label="Option+C",
        ),
        undo=HotkeyBinding(
            key_code=MAC_KEY_CODES["Z"],
            modifiers=CARBON_OPTION,
            label="Option+Z",
        ),
    )


def hotkey_presets() -> list[HotkeyBindings]:
    return [
        default_hotkey_bindings(),
        HotkeyBindings(
            capture=HotkeyBinding(
                MAC_KEY_CODES["C"], CARBON_CMD | CARBON_OPTION, "Command+Option+C"
            ),
            undo=HotkeyBinding(
                MAC_KEY_CODES["Z"], CARBON_CMD | CARBON_OPTION, "Command+Option+Z"
            ),
        ),
        HotkeyBindings(
            capture=HotkeyBinding(
                MAC_KEY_CODES["RETURN"], CARBON_CONTROL, "Control+Return"
            ),
            undo=HotkeyBinding(
                MAC_KEY_CODES["DELETE"], CARBON_CONTROL, "Control+Delete"
            ),
        ),
    ]


class MacScreenCaptureBackend:
    def __init__(self) -> None:
        app_services_path = find_library("ApplicationServices")
        carbon_path = find_library("Carbon")
        if not app_services_path or not carbon_path:
            raise RuntimeError("macOS screen capture frameworks are unavailable")
        self._app_services = ctypes.CDLL(app_services_path)
        self._carbon = ctypes.CDLL(carbon_path)
        self._configure_functions()
        self._event_handler_ref = ctypes.c_void_p()
        self._hotkey_refs: list[ctypes.c_void_p] = []
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._handler_proc = EventHandlerProc(self._handle_hotkey_event)

    def _configure_functions(self) -> None:
        self._app_services.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        self._app_services.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
        self._carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
        self._carbon.InstallEventHandler.argtypes = [
            ctypes.c_void_p,
            EventHandlerProc,
            ctypes.c_uint32,
            ctypes.POINTER(EventTypeSpec),
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._carbon.InstallEventHandler.restype = ctypes.c_int32
        self._carbon.RemoveEventHandler.argtypes = [ctypes.c_void_p]
        self._carbon.RemoveEventHandler.restype = ctypes.c_int32
        self._carbon.RegisterEventHotKey.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
            EventHotKeyID,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._carbon.RegisterEventHotKey.restype = ctypes.c_int32
        self._carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        self._carbon.UnregisterEventHotKey.restype = ctypes.c_int32
        self._carbon.GetEventParameter.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self._carbon.GetEventParameter.restype = ctypes.c_int32

    def permission_state(self) -> PermissionState:
        return (
            PermissionState.GRANTED
            if self._app_services.CGPreflightScreenCaptureAccess()
            else PermissionState.DENIED
        )

    def request_permission(self) -> PermissionState:
        return (
            PermissionState.GRANTED
            if self._app_services.CGRequestScreenCaptureAccess()
            else PermissionState.DENIED
        )

    def open_permission_settings(self) -> None:
        subprocess.Popen(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
            ]
        )

    def list_displays(self) -> list[CaptureDisplay]:
        displays: list[CaptureDisplay] = []
        for index, screen in enumerate(QGuiApplication.screens()):
            geometry = screen.geometry()
            identifier = f"qt-screen-{index}:{screen.name()}"
            displays.append(
                CaptureDisplay(
                    identifier=identifier,
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
            raise RuntimeError("macOS returned an empty screen capture")
        qimage = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
        width = qimage.width()
        height = qimage.height()
        rgba = bytes(qimage.bits())
        image = Image.frombuffer(
            "RGBA",
            (width, height),
            rgba,
            "raw",
            "RGBA",
            qimage.bytesPerLine(),
            1,
        ).copy()
        if image.width < region.width or image.height < region.height:
            raise RuntimeError("captured image dimensions are smaller than the selected region")
        return image

    def register_hotkeys(
        self,
        bindings: HotkeyBindings,
        on_capture: Callable[[], None],
        on_undo: Callable[[], None],
    ) -> None:
        self.unregister_hotkeys()
        event_type = EventTypeSpec(K_EVENT_CLASS_KEYBOARD, K_EVENT_HOTKEY_PRESSED)
        target = self._carbon.GetApplicationEventTarget()
        status = self._carbon.InstallEventHandler(
            target,
            self._handler_proc,
            1,
            ctypes.byref(event_type),
            None,
            ctypes.byref(self._event_handler_ref),
        )
        if status != 0:
            raise RuntimeError(f"could not install macOS hotkey handler ({status})")
        self._callbacks = {1: on_capture, 2: on_undo}
        try:
            for identifier, binding in ((1, bindings.capture), (2, bindings.undo)):
                reference = ctypes.c_void_p()
                hotkey_id = EventHotKeyID(HOTKEY_SIGNATURE, identifier)
                status = self._carbon.RegisterEventHotKey(
                    binding.key_code,
                    binding.modifiers,
                    hotkey_id,
                    target,
                    0,
                    ctypes.byref(reference),
                )
                if status != 0:
                    raise RuntimeError(f"hotkey {binding.label} is unavailable ({status})")
                self._hotkey_refs.append(reference)
        except Exception:
            self.unregister_hotkeys()
            raise

    def unregister_hotkeys(self) -> None:
        for reference in self._hotkey_refs:
            if reference:
                self._carbon.UnregisterEventHotKey(reference)
        self._hotkey_refs.clear()
        if self._event_handler_ref:
            self._carbon.RemoveEventHandler(self._event_handler_ref)
            self._event_handler_ref = ctypes.c_void_p()
        self._callbacks.clear()

    def _handle_hotkey_event(self, _call_ref, event_ref, _user_data) -> int:
        hotkey_id = EventHotKeyID()
        status = self._carbon.GetEventParameter(
            event_ref,
            K_EVENT_PARAM_DIRECT_OBJECT,
            TYPE_EVENT_HOTKEY_ID,
            None,
            ctypes.sizeof(hotkey_id),
            None,
            ctypes.byref(hotkey_id),
        )
        if status != 0 or hotkey_id.signature != HOTKEY_SIGNATURE:
            return EVENT_NOT_HANDLED
        callback = self._callbacks.get(hotkey_id.identifier)
        if callback is None:
            return EVENT_NOT_HANDLED
        callback()
        return 0

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
