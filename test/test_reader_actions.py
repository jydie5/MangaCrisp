from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import Qt

from mangacrisp_app.reader_actions import (
    READER_ACTIONS,
    action_keycap,
    help_entries,
    overlay_action_ids,
    reader_bindings,
    resolve_action,
)
from mangacrisp_app.viewer import SpreadWindow

AVAILABLE = frozenset({"always", "bookmark_add", "bookmark_list"})
WITHOUT_BOOKMARKS = frozenset({"always"})


def test_directional_bindings_and_keycaps_share_the_same_direction_contract() -> None:
    assert action_keycap("next", "rtl") == "←"
    assert action_keycap("previous", "rtl") == "→"
    assert resolve_action("left", frozenset(), "rtl", AVAILABLE) == "next"
    assert resolve_action("right", frozenset(), "rtl", AVAILABLE) == "previous"
    assert resolve_action("left", frozenset({"shift"}), "rtl", AVAILABLE) == "forward_one"

    assert action_keycap("next", "ltr") == "→"
    assert action_keycap("previous", "ltr") == "←"
    assert resolve_action("right", frozenset(), "ltr", AVAILABLE) == "next"
    assert resolve_action("left", frozenset(), "ltr", AVAILABLE) == "previous"
    assert resolve_action("right", frozenset({"shift"}), "ltr", AVAILABLE) == "forward_one"


def test_help_and_overlay_hide_unavailable_bookmark_actions() -> None:
    help_action_ids = {entry.action_id for entry in help_entries("rtl", WITHOUT_BOOKMARKS)}
    assert "bookmark" not in help_action_ids
    assert "bookmarks" not in help_action_ids
    assert "bookmark" not in overlay_action_ids(WITHOUT_BOOKMARKS, "rtl")
    assert "bookmarks" not in overlay_action_ids(WITHOUT_BOOKMARKS, "rtl")

    available_help_ids = {entry.action_id for entry in help_entries("rtl", AVAILABLE)}
    assert {"bookmark", "bookmarks"} <= available_help_ids
    assert {"bookmark", "bookmarks"} <= set(overlay_action_ids(AVAILABLE, "rtl"))


def test_exact_modifiers_preserve_text_and_popup_input_boundaries() -> None:
    assert resolve_action("t", frozenset(), "rtl", AVAILABLE) == "pages"
    assert resolve_action("t", frozenset({"shift"}), "rtl", AVAILABLE) is None
    assert resolve_action("b", frozenset(), "rtl", AVAILABLE) == "bookmark"
    assert resolve_action("b", frozenset({"shift"}), "rtl", AVAILABLE) == "bookmarks"
    assert resolve_action("b", frozenset(), "rtl", WITHOUT_BOOKMARKS) is None
    assert resolve_action("question", frozenset(), "rtl", AVAILABLE) == "help"
    assert resolve_action("question", frozenset({"shift"}), "rtl", AVAILABLE) == "help"
    assert resolve_action("left", frozenset({"control"}), "rtl", AVAILABLE) is None


def test_shift_variants_that_the_previous_handler_accepted_still_dispatch() -> None:
    assert resolve_action("space", frozenset({"shift"}), "rtl", AVAILABLE) == "next"
    assert resolve_action("backspace", frozenset({"shift"}), "rtl", AVAILABLE) == "previous"
    assert resolve_action("escape", frozenset({"shift"}), "rtl", AVAILABLE) == "escape"


def test_every_declared_action_has_a_directional_binding_and_zoom_group_is_explicit() -> None:
    for direction in ("rtl", "ltr"):
        bound_actions = {binding.action_id for binding in reader_bindings(direction)}
        assert set(READER_ACTIONS) <= bound_actions
        assert resolve_action("plus", frozenset(), direction, AVAILABLE) == "zoom_in"
        assert resolve_action("minus", frozenset(), direction, AVAILABLE) == "zoom_out"
        assert resolve_action("0", frozenset(), direction, AVAILABLE) == "fit"
        assert resolve_action("w", frozenset(), direction, AVAILABLE) == "width"
        assert resolve_action("1", frozenset(), direction, AVAILABLE) == "actual"


def test_keypad_modifier_keeps_existing_arrow_and_zoom_behavior(qapp, tmp_path: Path) -> None:
    pages = []
    for index in range(2):
        page = tmp_path / f"{index}.png"
        Image.new("RGB", (24, 36), "white").save(page)
        pages.append(page)
    window = SpreadWindow(pages, "keypad", auto_prefetch=False, settings_path=tmp_path / "settings.json")
    try:
        with patch.object(window, "move_by") as move:
            assert window.handle_navigation_key(Qt.Key_Left, Qt.KeypadModifier)
            move.assert_called_once_with(window.page_turn_step())
        with patch.object(window, "zoom_in") as zoom:
            assert not window.handle_navigation_key(Qt.Key_Plus, Qt.KeypadModifier)
            zoom.assert_not_called()
    finally:
        window.close()
        qapp.processEvents()

