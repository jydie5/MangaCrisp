from __future__ import annotations

from dataclasses import dataclass

CURSOR_AUTO_HIDE_DELAY_MS = 2000


@dataclass(frozen=True)
class CursorAutoHideState:
    """Snapshot of the reader state that decides whether the cursor may disappear."""

    fullscreen: bool
    window_active: bool = True
    drag_active: bool = False
    modal_open: bool = False
    pointer_over_overlay: bool = False
    closing: bool = False


def cursor_may_hide(state: CursorAutoHideState) -> bool:
    """Return True when an idle cursor on the image area should be hidden."""
    if not state.fullscreen or state.closing:
        return False
    if not state.window_active or state.drag_active or state.modal_open:
        return False
    return not state.pointer_over_overlay


def cursor_must_show(state: CursorAutoHideState) -> bool:
    """Return True when a hidden cursor has to come back regardless of idle time."""
    return not cursor_may_hide(state)
