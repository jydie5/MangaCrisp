from __future__ import annotations

import ctypes
import ctypes.util
import itertools
import os
import select
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image
from PySide6.QtCore import QCoreApplication, QEventLoop
from PySide6.QtGui import QGuiApplication, QImage

from mangacrisp_app.branding import APP_BUNDLE_IDENTIFIER
from mangacrisp_app.platform.capture_base import (
    CaptureDisplay,
    CaptureRect,
    HotkeyBinding,
    HotkeyBindings,
    PermissionState,
)

# X11 modifier masks. They double as the portable modifier encoding for the
# Wayland GlobalShortcuts portal triggers.
SHIFT_MASK = 1 << 0
LOCK_MASK = 1 << 1
CONTROL_MASK = 1 << 2
MOD1_MASK = 1 << 3  # Alt
MOD2_MASK = 1 << 4  # NumLock
MOD4_MASK = 1 << 6  # Super

XK_C = 0x0063
XK_U = 0x0075
XK_Z = 0x007A
XK_RETURN = 0xFF0D
XK_DELETE = 0xFFFF

KEYSYM_NAMES = {
    XK_C: "c",
    XK_U: "u",
    XK_Z: "z",
    XK_RETURN: "Return",
    XK_DELETE: "Delete",
}
PORTAL_MODIFIERS = (
    (CONTROL_MASK, "CTRL"),
    (MOD1_MASK, "ALT"),
    (SHIFT_MASK, "SHIFT"),
    (MOD4_MASK, "LOGO"),
)

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
PERMISSION_STORE_BUS_NAME = "org.freedesktop.impl.portal.PermissionStore"
PERMISSION_STORE_PATH = "/org/freedesktop/impl/portal/PermissionStore"
SCREENSHOT_TIMEOUT_SECONDS = 10.0
PERMISSION_TIMEOUT_SECONDS = 120.0
SHORTCUT_TIMEOUT_SECONDS = 120.0
IMMEDIATE_REFUSAL_SECONDS = 0.5

_TOKENS = itertools.count(1)


def default_hotkey_bindings() -> HotkeyBindings:
    return HotkeyBindings(
        capture=HotkeyBinding(XK_C, MOD1_MASK, "Alt+C"),
        undo=HotkeyBinding(XK_U, MOD1_MASK, "Alt+U"),
    )


def hotkey_presets() -> list[HotkeyBindings]:
    return [
        default_hotkey_bindings(),
        HotkeyBindings(
            capture=HotkeyBinding(XK_C, CONTROL_MASK | MOD1_MASK, "Control+Alt+C"),
            undo=HotkeyBinding(XK_Z, CONTROL_MASK | MOD1_MASK, "Control+Alt+Z"),
        ),
        HotkeyBindings(
            capture=HotkeyBinding(XK_RETURN, CONTROL_MASK, "Control+Return"),
            undo=HotkeyBinding(XK_DELETE, CONTROL_MASK, "Control+Delete"),
        ),
    ]


def portal_trigger(binding: HotkeyBinding) -> str:
    """Format a binding as an XDG shortcuts-spec trigger such as ``ALT+c``."""
    parts = [name for mask, name in PORTAL_MODIFIERS if binding.modifiers & mask]
    parts.append(KEYSYM_NAMES[binding.key_code])
    return "+".join(parts)


def is_wayland_session(environ: dict[str, str] | None = None) -> bool:
    environment = os.environ if environ is None else environ
    if environment.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return True
    return bool(environment.get("WAYLAND_DISPLAY"))


def qt_displays() -> list[CaptureDisplay]:
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


def validate_region(region: CaptureRect, displays: list[CaptureDisplay]) -> CaptureDisplay:
    display = next((item for item in displays if item.identifier == region.display_id), None)
    if display is None:
        raise RuntimeError("selected display is no longer available")
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
    return display


def crop_desktop_image(
    image: Image.Image,
    region: CaptureRect,
    displays: list[CaptureDisplay],
) -> Image.Image:
    """Crop a whole-desktop screenshot to a region in Qt logical coordinates.

    Compositors return the desktop in physical pixels, so the logical virtual
    desktop is scaled to the image size before cropping.
    """
    left = min(display.x for display in displays)
    top = min(display.y for display in displays)
    right = max(display.x + display.width for display in displays)
    bottom = max(display.y + display.height for display in displays)
    scale_x = image.width / (right - left)
    scale_y = image.height / (bottom - top)
    box = (
        round((region.x - left) * scale_x),
        round((region.y - top) * scale_y),
        round((region.x + region.width - left) * scale_x),
        round((region.y + region.height - top) * scale_y),
    )
    return image.crop(box).convert("RGBA")


def run_while_processing_events(function: Callable[[], object]) -> object:
    """Run a blocking portal call without freezing the Qt user interface."""
    if QCoreApplication.instance() is None:
        return function()
    outcome: dict[str, object] = {}

    def worker() -> None:
        try:
            outcome["value"] = function()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the Qt thread.
            outcome["error"] = exc

    thread = threading.Thread(target=worker, name="MangaCrisp portal", daemon=True)
    thread.start()
    while thread.is_alive():
        QCoreApplication.processEvents(QEventLoop.AllEvents, 30)
        thread.join(0.01)
    if "error" in outcome:
        raise outcome["error"]  # type: ignore[misc]
    return outcome.get("value")


class PortalError(RuntimeError):
    pass


class _PortalConnection:
    """A jeepney session-bus connection that speaks the XDG Request pattern."""

    def __init__(self) -> None:
        from jeepney.io.blocking import open_dbus_connection

        self.connection = open_dbus_connection(bus="SESSION")
        self._register_application()

    def close(self) -> None:
        with suppress(Exception):
            self.connection.close()

    def _register_application(self) -> None:
        # Host (unsandboxed) apps must register before other portal calls so
        # that permissions are stored for MangaCrisp rather than for the
        # launching process. This fails harmlessly when the .desktop file is
        # not installed, in which case the portal infers an app ID.
        with suppress(Exception):
            self.call(
                "org.freedesktop.host.portal.Registry",
                "Register",
                "sa{sv}",
                (APP_BUNDLE_IDENTIFIER, {}),
            )

    def call(
        self,
        interface: str,
        method: str,
        signature: str,
        body: tuple,
        *,
        path: str = PORTAL_PATH,
        bus_name: str = PORTAL_BUS_NAME,
    ):
        from jeepney import DBusAddress, MessageType, new_method_call

        address = DBusAddress(path, bus_name=bus_name, interface=interface)
        reply = self.connection.send_and_get_reply(
            new_method_call(address, method, signature, body), timeout=10
        )
        if reply.header.message_type == MessageType.error:
            detail = reply.body[0] if reply.body else "unknown error"
            raise PortalError(f"{interface}.{method} failed: {detail}")
        return reply.body

    def get_property(self, interface: str, name: str):
        body = self.call(
            "org.freedesktop.DBus.Properties",
            "Get",
            "ss",
            (interface, name),
        )
        return body[0][1]

    def request(
        self,
        interface: str,
        method: str,
        signature: str,
        arguments: tuple,
        options: dict,
        *,
        timeout: float,
    ) -> dict:
        from jeepney import MatchRule
        from jeepney.bus_messages import message_bus

        token = f"mangacrisp{next(_TOKENS)}"
        sender = self.connection.unique_name.lstrip(":").replace(".", "_")
        handle = f"{PORTAL_PATH}/request/{sender}/{token}"
        rule = MatchRule(
            type="signal",
            interface="org.freedesktop.portal.Request",
            member="Response",
            path=handle,
        )
        self.connection.send_and_get_reply(message_bus.AddMatch(rule), timeout=10)
        try:
            with self.connection.filter(rule) as queue:
                self.call(
                    interface,
                    method,
                    signature + "a{sv}",
                    (*arguments, {**options, "handle_token": ("s", token)}),
                )
                try:
                    signal = self.connection.recv_until_filtered(queue, timeout=timeout)
                except TimeoutError as exc:
                    raise PortalError(f"{method} did not respond in {timeout:.0f}s") from exc
        finally:
            with suppress(Exception):
                self.connection.send_and_get_reply(message_bus.RemoveMatch(rule), timeout=10)
        code, results = signal.body
        if code == 1:
            raise PermissionError(f"{method} was cancelled")
        if code != 0:
            raise PermissionError(f"{method} was denied")
        return {key: value for key, (_signature, value) in results.items()}


class _PortalShortcutListener(threading.Thread):
    """Owns a GlobalShortcuts portal session and dispatches activations."""

    def __init__(self, triggers: dict[str, tuple[str, str]], callbacks: dict[str, Callable[[], None]]) -> None:
        super().__init__(name="MangaCrisp shortcuts", daemon=True)
        self.triggers = triggers
        self.callbacks = callbacks
        self.ready = threading.Event()
        self.stop_requested = threading.Event()
        self.error: BaseException | None = None

    def run(self) -> None:
        try:
            portal = _PortalConnection()
        except BaseException as exc:  # noqa: BLE001 - reported to the Qt thread.
            self.error = exc
            self.ready.set()
            return
        session_handle = ""
        try:
            session_handle = self._bind(portal)
            self.ready.set()
            self._listen(portal, session_handle)
        except BaseException as exc:  # noqa: BLE001 - reported to the Qt thread.
            self.error = exc
            self.ready.set()
        finally:
            if session_handle:
                with suppress(Exception):
                    portal.call(
                        "org.freedesktop.portal.Session",
                        "Close",
                        "",
                        (),
                        path=session_handle,
                    )
            portal.close()

    def _bind(self, portal: _PortalConnection) -> str:
        interface = "org.freedesktop.portal.GlobalShortcuts"
        try:
            portal.get_property(interface, "version")
        except PortalError as exc:
            raise RuntimeError("this desktop does not provide global shortcuts") from exc
        created = portal.request(
            interface,
            "CreateSession",
            "",
            (),
            {"session_handle_token": ("s", f"mangacrisp{next(_TOKENS)}")},
            timeout=SHORTCUT_TIMEOUT_SECONDS,
        )
        session_handle = str(created["session_handle"])
        shortcuts = [
            (
                identifier,
                {
                    "description": ("s", description),
                    "preferred_trigger": ("s", trigger),
                },
            )
            for identifier, (description, trigger) in self.triggers.items()
        ]
        portal.request(
            interface,
            "BindShortcuts",
            "oa(sa{sv})s",
            (session_handle, shortcuts, ""),
            {},
            timeout=SHORTCUT_TIMEOUT_SECONDS,
        )
        return session_handle

    def _listen(self, portal: _PortalConnection, session_handle: str) -> None:
        from jeepney import MatchRule
        from jeepney.bus_messages import message_bus

        rule = MatchRule(
            type="signal",
            interface="org.freedesktop.portal.GlobalShortcuts",
            member="Activated",
            path=PORTAL_PATH,
        )
        portal.connection.send_and_get_reply(message_bus.AddMatch(rule), timeout=10)
        with portal.connection.filter(rule) as queue:
            while not self.stop_requested.is_set():
                try:
                    signal = portal.connection.recv_until_filtered(queue, timeout=0.25)
                except TimeoutError:
                    continue
                handle, shortcut_id = str(signal.body[0]), str(signal.body[1])
                callback = self.callbacks.get(shortcut_id)
                if handle == session_handle and callback is not None:
                    callback()


class _XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class _XEvent(ctypes.Union):
    _fields_ = (("type", ctypes.c_int), ("xkey", _XKeyEvent), ("pad", ctypes.c_long * 24))


class _XErrorEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("resourceid", ctypes.c_ulong),
        ("serial", ctypes.c_ulong),
        ("error_code", ctypes.c_ubyte),
        ("request_code", ctypes.c_ubyte),
        ("minor_code", ctypes.c_ubyte),
    ]


_X_ERROR_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(_XErrorEvent))
X_KEY_PRESS = 2
X_BAD_ACCESS = 10
X_GRAB_MODE_ASYNC = 1
# Grab each shortcut with and without CapsLock and NumLock so that lock keys do
# not disable it.
X_IGNORED_MODIFIERS = (0, LOCK_MASK, MOD2_MASK, LOCK_MASK | MOD2_MASK)


class _X11ShortcutListener(threading.Thread):
    """Grabs keys on a private Xlib connection and dispatches presses."""

    def __init__(self, bindings: dict[str, HotkeyBinding], callbacks: dict[str, Callable[[], None]]) -> None:
        super().__init__(name="MangaCrisp X11 shortcuts", daemon=True)
        self.bindings = bindings
        self.callbacks = callbacks
        self.ready = threading.Event()
        self.stop_requested = threading.Event()
        self.error: BaseException | None = None

    def run(self) -> None:
        library = ctypes.util.find_library("X11")
        if library is None:
            self.error = RuntimeError("libX11 is required for global shortcuts")
            self.ready.set()
            return
        xlib = ctypes.CDLL(library)
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XDefaultRootWindow.restype = ctypes.c_ulong
        xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        xlib.XKeysymToKeycode.restype = ctypes.c_ubyte
        xlib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xlib.XGrabKey.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
        ]
        xlib.XUngrabKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong]
        xlib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        xlib.XPending.argtypes = [ctypes.c_void_p]
        xlib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.POINTER(_XEvent)]
        xlib.XConnectionNumber.argtypes = [ctypes.c_void_p]
        xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xlib.XSetErrorHandler.restype = ctypes.c_void_p
        xlib.XSetErrorHandler.argtypes = [ctypes.c_void_p]

        display = xlib.XOpenDisplay(None)
        if not display:
            self.error = RuntimeError("cannot connect to the X server")
            self.ready.set()
            return
        root = xlib.XDefaultRootWindow(display)
        grabs: list[tuple[int, int]] = []
        keymap: dict[tuple[int, int], str] = {}
        access_errors: list[int] = []

        @_X_ERROR_HANDLER
        def on_error(_display, event):
            access_errors.append(int(event.contents.error_code))
            return 0

        previous_handler = xlib.XSetErrorHandler(ctypes.cast(on_error, ctypes.c_void_p))
        try:
            for identifier, binding in self.bindings.items():
                keycode = xlib.XKeysymToKeycode(display, binding.key_code)
                if keycode == 0:
                    raise RuntimeError(f"hotkey {binding.label} has no key on this keyboard")
                keymap[(keycode, binding.modifiers)] = identifier
                for ignored in X_IGNORED_MODIFIERS:
                    modifiers = binding.modifiers | ignored
                    xlib.XGrabKey(
                        display, keycode, modifiers, root, 1, X_GRAB_MODE_ASYNC, X_GRAB_MODE_ASYNC
                    )
                    grabs.append((keycode, modifiers))
                xlib.XSync(display, 0)
                if X_BAD_ACCESS in access_errors:
                    raise RuntimeError(f"hotkey {binding.label} is used by another application")
            self.ready.set()
            descriptor = xlib.XConnectionNumber(display)
            event = _XEvent()
            relevant = SHIFT_MASK | CONTROL_MASK | MOD1_MASK | MOD4_MASK
            while not self.stop_requested.is_set():
                if not xlib.XPending(display):
                    select.select([descriptor], [], [], 0.25)
                    continue
                xlib.XNextEvent(display, ctypes.byref(event))
                if event.type != X_KEY_PRESS:
                    continue
                key = (int(event.xkey.keycode), int(event.xkey.state) & relevant)
                callback = self.callbacks.get(keymap.get(key, ""))
                if callback is not None:
                    callback()
        except BaseException as exc:  # noqa: BLE001 - reported to the Qt thread.
            self.error = exc
            self.ready.set()
        finally:
            for keycode, modifiers in grabs:
                xlib.XUngrabKey(display, keycode, modifiers, root)
            xlib.XSync(display, 0)
            xlib.XSetErrorHandler(previous_handler)
            xlib.XCloseDisplay(display)


class LinuxScreenCaptureBackend:
    def __init__(self, *, wayland: bool | None = None) -> None:
        self.wayland = is_wayland_session() if wayland is None else wayland
        self._portal: _PortalConnection | None = None
        self._portal_lock = threading.Lock()
        self._screenshot_granted = False
        self._listener: _PortalShortcutListener | _X11ShortcutListener | None = None

    # Permissions -----------------------------------------------------------

    def permission_state(self) -> PermissionState:
        if not self.wayland or self._screenshot_granted:
            return PermissionState.GRANTED
        if self._stored_screenshot_permission() == "yes":
            return PermissionState.GRANTED
        return PermissionState.DENIED

    def request_permission(self) -> PermissionState:
        if not self.wayland:
            return PermissionState.GRANTED
        # The first portal screenshot shows the desktop's permission dialog.
        # GNOME only shows it while MangaCrisp has focus, which is the case
        # when the user presses the start button. The very first request of a
        # newly registered app is sometimes refused without a dialog, so an
        # immediate refusal is retried once.
        for attempt in range(2):
            started = time.monotonic()
            try:
                self._portal_screenshot(PERMISSION_TIMEOUT_SECONDS)
            except (PermissionError, PortalError):
                if attempt == 0 and time.monotonic() - started < IMMEDIATE_REFUSAL_SECONDS:
                    continue
                return PermissionState.DENIED
            return PermissionState.GRANTED
        return PermissionState.DENIED

    def open_permission_settings(self) -> None:
        # Portal permissions have no single settings page across desktops;
        # GNOME shows them under Settings > Apps.
        return None

    def _stored_screenshot_permission(self) -> str | None:
        try:
            body = self._call_portal(
                lambda portal: portal.call(
                    "org.freedesktop.impl.portal.PermissionStore",
                    "Lookup",
                    "ss",
                    ("screenshot", "screenshot"),
                    path=PERMISSION_STORE_PATH,
                    bus_name=PERMISSION_STORE_BUS_NAME,
                )
            )
        except Exception:  # noqa: BLE001 - absent store means unknown.
            return None
        values = body[0].get(APP_BUNDLE_IDENTIFIER)
        return values[0] if values else None

    # Capture ---------------------------------------------------------------

    def list_displays(self) -> list[CaptureDisplay]:
        return qt_displays()

    def capture_region(self, region: CaptureRect) -> Image.Image:
        displays = self.list_displays()
        display = validate_region(region, displays)
        if self.wayland:
            desktop = self._portal_screenshot(SCREENSHOT_TIMEOUT_SECONDS)
            return crop_desktop_image(desktop, region, displays)
        return self._grab_x11(region, display)

    def _grab_x11(self, region: CaptureRect, display: CaptureDisplay) -> Image.Image:
        index = next(
            index for index, item in enumerate(self.list_displays()) if item.identifier == display.identifier
        )
        screen = QGuiApplication.screens()[index]
        pixmap = screen.grabWindow(0, region.x - display.x, region.y - display.y, region.width, region.height)
        if pixmap.isNull():
            raise RuntimeError("the X server returned an empty screen capture")
        qimage = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
        return Image.frombuffer(
            "RGBA",
            (qimage.width(), qimage.height()),
            bytes(qimage.bits()),
            "raw",
            "RGBA",
            qimage.bytesPerLine(),
            1,
        ).copy()

    def _call_portal(self, function):
        with self._portal_lock:
            if self._portal is None:
                self._portal = _PortalConnection()
            return function(self._portal)

    def _portal_screenshot(self, timeout: float) -> Image.Image:
        def take() -> Image.Image:
            results = self._call_portal(
                lambda portal: portal.request(
                    "org.freedesktop.portal.Screenshot",
                    "Screenshot",
                    "s",
                    ("",),
                    {"interactive": ("b", False), "modal": ("b", False)},
                    timeout=timeout,
                )
            )
            path = Path(unquote(urlparse(str(results["uri"])).path))
            try:
                with Image.open(path) as image:
                    return image.convert("RGBA")
            finally:
                # The portal writes a new file for every request; it is not
                # part of the user's screenshot history.
                path.unlink(missing_ok=True)

        image = run_while_processing_events(take)
        self._screenshot_granted = True
        return image  # type: ignore[return-value]

    # Shortcuts -------------------------------------------------------------

    def register_hotkeys(
        self,
        bindings: HotkeyBindings,
        on_capture: Callable[[], None],
        on_undo: Callable[[], None],
    ) -> None:
        self.unregister_hotkeys()
        callbacks = {"capture": on_capture, "undo": on_undo}
        if self.wayland:
            listener: _PortalShortcutListener | _X11ShortcutListener = _PortalShortcutListener(
                {
                    "capture": ("Capture the selected region", portal_trigger(bindings.capture)),
                    "undo": ("Undo the last capture", portal_trigger(bindings.undo)),
                },
                callbacks,
            )
            timeout = SHORTCUT_TIMEOUT_SECONDS + 5
        else:
            listener = _X11ShortcutListener(
                {"capture": bindings.capture, "undo": bindings.undo},
                callbacks,
            )
            timeout = 10.0
        listener.start()
        run_while_processing_events(lambda: listener.ready.wait(timeout))
        if listener.error is not None or not listener.ready.is_set():
            listener.stop_requested.set()
            raise RuntimeError(str(listener.error or "global shortcuts did not respond"))
        self._listener = listener

    def unregister_hotkeys(self) -> None:
        listener, self._listener = self._listener, None
        if listener is None:
            return
        listener.stop_requested.set()
        listener.join(2)

    def __del__(self) -> None:
        with suppress(Exception):
            self.unregister_hotkeys()
        if self._portal is not None:
            self._portal.close()
