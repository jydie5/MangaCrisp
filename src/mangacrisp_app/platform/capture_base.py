from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from PIL import Image


class PermissionState(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class CaptureDisplay:
    identifier: str
    name: str
    x: int
    y: int
    width: int
    height: int
    scale: float = 1.0


@dataclass(frozen=True)
class CaptureRect:
    display_id: str
    x: int
    y: int
    width: int
    height: int

    def is_valid(self) -> bool:
        return self.width >= 2 and self.height >= 2


@dataclass(frozen=True)
class HotkeyBinding:
    key_code: int
    modifiers: int
    label: str


@dataclass(frozen=True)
class HotkeyBindings:
    capture: HotkeyBinding
    undo: HotkeyBinding


class ScreenCaptureBackend(Protocol):
    def permission_state(self) -> PermissionState: ...

    def request_permission(self) -> PermissionState: ...

    def open_permission_settings(self) -> None: ...

    def list_displays(self) -> list[CaptureDisplay]: ...

    def capture_region(self, region: CaptureRect) -> Image.Image: ...

    def register_hotkeys(
        self,
        bindings: HotkeyBindings,
        on_capture: Callable[[], None],
        on_undo: Callable[[], None],
    ) -> None: ...

    def unregister_hotkeys(self) -> None: ...
