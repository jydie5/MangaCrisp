from __future__ import annotations

import sys

from mangacrisp_app.platform.capture_base import ScreenCaptureBackend

if sys.platform == "darwin":
    from mangacrisp_app.platform.macos import (
        application_directories,
        bundled_archive_tool_candidates,
        engine_executable_names,
        open_directory,
        subprocess_window_kwargs,
    )
elif sys.platform == "win32":
    from mangacrisp_app.platform.windows import (
        application_directories,
        bundled_archive_tool_candidates,
        engine_executable_names,
        open_directory,
        subprocess_window_kwargs,
    )
else:
    from mangacrisp_app.platform.common import (
        application_directories,
        bundled_archive_tool_candidates,
        engine_executable_names,
        open_directory,
        subprocess_window_kwargs,
    )

__all__ = [
    "application_directories",
    "bundled_archive_tool_candidates",
    "engine_executable_names",
    "open_directory",
    "subprocess_window_kwargs",
]


def create_screen_capture_backend() -> ScreenCaptureBackend:
    if sys.platform == "darwin":
        from mangacrisp_app.platform.capture_macos import MacScreenCaptureBackend

        return MacScreenCaptureBackend()
    if sys.platform == "win32":
        from mangacrisp_app.platform.capture_windows import WindowsScreenCaptureBackend

        return WindowsScreenCaptureBackend()
    raise RuntimeError("Screen Capture v1 is currently available on macOS only")


def screen_capture_hotkey_presets() -> list:
    if sys.platform == "darwin":
        from mangacrisp_app.platform.capture_macos import hotkey_presets

        return hotkey_presets()
    if sys.platform == "win32":
        from mangacrisp_app.platform.capture_windows import hotkey_presets

        return hotkey_presets()
    return []


__all__.extend(["create_screen_capture_backend", "screen_capture_hotkey_presets"])
