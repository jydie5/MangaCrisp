"""End-to-end X11 capture check on a private Xvfb server.

Runs only where ``xvfb-run`` and libXtst are available (the Linux CI installs
them). XTest injects real key events so the XGrabKey path is exercised.
"""

from __future__ import annotations

import ctypes.util
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux")
    or shutil.which("xvfb-run") is None
    or ctypes.util.find_library("Xtst") is None,
    reason="needs Linux with xvfb-run and libXtst",
)

SCRIPT = textwrap.dedent(
    """
    import ctypes, ctypes.util, sys, time
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication, QWidget
    from mangacrisp_app.platform import create_screen_capture_backend, screen_capture_hotkey_presets
    from mangacrisp_app.platform.capture_base import CaptureRect

    app = QApplication(sys.argv)
    backend = create_screen_capture_backend()
    assert backend.wayland is False
    window = QWidget()
    palette = window.palette()
    palette.setColor(QPalette.Window, QColor(200, 30, 40))
    window.setPalette(palette)
    window.setAutoFillBackground(True)
    window.setGeometry(50, 60, 300, 200)
    window.show()
    events = []

    def run():
        display = backend.list_displays()[0]
        image = backend.capture_region(CaptureRect(display.identifier, 100, 100, 50, 40))
        print("SIZE", image.size)
        print("PIXEL", image.getpixel((10, 10)))
        backend.register_hotkeys(
            screen_capture_hotkey_presets()[0],
            lambda: events.append("capture"),
            lambda: events.append("undo"),
        )
        xlib = ctypes.CDLL(ctypes.util.find_library("X11"))
        xtest = ctypes.CDLL(ctypes.util.find_library("Xtst"))
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        xlib.XFlush.argtypes = [ctypes.c_void_p]
        xtest.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        connection = xlib.XOpenDisplay(None)

        def press(*keysyms):
            codes = [xlib.XKeysymToKeycode(connection, keysym) for keysym in keysyms]
            for code in codes:
                xtest.XTestFakeKeyEvent(connection, code, 1, 0)
            for code in reversed(codes):
                xtest.XTestFakeKeyEvent(connection, code, 0, 0)
            xlib.XFlush(connection)
            time.sleep(0.3)

        alt, key_c, key_u = 0xFFE9, 0x63, 0x75
        press(alt, key_c)
        press(alt, key_c)
        press(alt, key_u)
        press(key_c)
        QTimer.singleShot(800, finish)

    def finish():
        print("EVENTS", ",".join(events))
        backend.unregister_hotkeys()
        app.quit()

    QTimer.singleShot(500, run)
    app.exec()
    """
)


def test_x11_capture_and_global_shortcuts() -> None:
    environment = {key: value for key, value in os.environ.items() if key != "WAYLAND_DISPLAY"}
    environment.update({"XDG_SESSION_TYPE": "x11", "QT_QPA_PLATFORM": "xcb", "MANGACRISP_LANGUAGE": "en"})
    completed = subprocess.run(
        ["xvfb-run", "-a", "-s", "-screen 0 1280x800x24", sys.executable, "-c", SCRIPT],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    output = completed.stdout

    assert completed.returncode == 0, completed.stderr[-2000:]
    assert "SIZE (50, 40)" in output
    assert "PIXEL (200, 30, 40, 255)" in output
    assert "EVENTS capture,capture,undo" in output
