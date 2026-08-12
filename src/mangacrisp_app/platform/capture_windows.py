from __future__ import annotations


class WindowsScreenCaptureBackend:
    def __init__(self) -> None:
        raise RuntimeError("Screen Capture v1 is currently available on macOS only")


def hotkey_presets() -> list:
    return []

