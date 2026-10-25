"""Qt-independent definitions for the reader's built-in actions and keys.

The reader keeps focus and modal handling in :mod:`viewer`.  This module only
describes the stable, shared vocabulary used by key dispatch, keycaps, and
shortcut help so those surfaces cannot quietly drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReaderAction:
    id: str
    label: str
    availability: str = "always"


@dataclass(frozen=True)
class ReaderBinding:
    action_id: str
    key: str
    modifiers: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ReaderHelpEntry:
    action_id: str | None
    template: str
    keys: str | None = None


READER_ACTIONS = {
    action.id: action
    for action in (
        ReaderAction("next", "次へ"),
        ReaderAction("previous", "前へ"),
        ReaderAction("forward_one", "＋1"),
        ReaderAction("back_one", "−1"),
        ReaderAction("settings", "設定"),
        ReaderAction("original", "原画と比較"),
        ReaderAction("fullscreen", "全画面"),
        ReaderAction("layout", "見開き"),
        ReaderAction("help", "操作一覧"),
        ReaderAction("bookmark", "しおり", "bookmark_add"),
        ReaderAction("bookmarks", "しおり一覧", "bookmark_list"),
        ReaderAction("pages", "ページ一覧"),
        ReaderAction("zoom_in", "拡大"),
        ReaderAction("zoom_out", "縮小"),
        ReaderAction("fit", "全体に合わせる"),
        ReaderAction("width", "幅に合わせる"),
        ReaderAction("actual", "実寸"),
        ReaderAction("escape", "閉じる"),
    )
}


def action_label(action_id: str) -> str:
    return READER_ACTIONS[action_id].label


def is_action_available(action_id: str, available: frozenset[str]) -> bool:
    return READER_ACTIONS[action_id].availability in available


def _direction_keys(reading_direction: str) -> tuple[str, str]:
    return ("left", "right") if reading_direction == "rtl" else ("right", "left")


def action_keycap(action_id: str, reading_direction: str) -> str:
    next_key, previous_key = _direction_keys(reading_direction)
    keycaps = {
        "next": "←" if next_key == "left" else "→",
        "previous": "←" if previous_key == "left" else "→",
        "forward_one": "Shift+←" if next_key == "left" else "Shift+→",
        "back_one": "Shift+←" if previous_key == "left" else "Shift+→",
        "settings": "P",
        "original": "O",
        "fullscreen": "F",
        "layout": "V",
        "help": "H",
        "bookmark": "B",
        "bookmarks": "Shift+B",
        "pages": "T",
        "zoom_in": "+",
        "zoom_out": "−",
        "fit": "0",
        "width": "W",
        "actual": "1",
        "escape": "Esc",
    }
    return keycaps[action_id]


def reader_bindings(reading_direction: str) -> tuple[ReaderBinding, ...]:
    next_key, previous_key = _direction_keys(reading_direction)
    bindings = [
        ReaderBinding("zoom_in", "plus"),
        ReaderBinding("zoom_in", "plus", frozenset({"shift"})),
        ReaderBinding("zoom_in", "equal"),
        ReaderBinding("zoom_in", "equal", frozenset({"shift"})),
        ReaderBinding("zoom_out", "minus"),
        ReaderBinding("fit", "0"),
        ReaderBinding("width", "w"),
        ReaderBinding("actual", "1"),
        ReaderBinding("forward_one", next_key, frozenset({"shift"})),
        ReaderBinding("forward_one", "down", frozenset({"shift"})),
        ReaderBinding("back_one", previous_key, frozenset({"shift"})),
        ReaderBinding("back_one", "up", frozenset({"shift"})),
        ReaderBinding("next", next_key),
        ReaderBinding("next", "down"),
        ReaderBinding("next", "space"),
        ReaderBinding("next", "space", frozenset({"shift"})),
        ReaderBinding("previous", previous_key),
        ReaderBinding("previous", "up"),
        ReaderBinding("previous", "backspace"),
        ReaderBinding("previous", "backspace", frozenset({"shift"})),
        ReaderBinding("forward_one", "e"),
        ReaderBinding("forward_one", "e", frozenset({"shift"})),
        ReaderBinding("back_one", "q"),
        ReaderBinding("back_one", "q", frozenset({"shift"})),
        ReaderBinding("fullscreen", "f"),
        ReaderBinding("fullscreen", "f", frozenset({"shift"})),
        ReaderBinding("settings", "p"),
        ReaderBinding("settings", "p", frozenset({"shift"})),
        ReaderBinding("layout", "v"),
        ReaderBinding("layout", "v", frozenset({"shift"})),
        ReaderBinding("original", "o"),
        ReaderBinding("original", "o", frozenset({"shift"})),
        ReaderBinding("bookmarks", "b", frozenset({"shift"})),
        ReaderBinding("bookmark", "b"),
        ReaderBinding("pages", "t"),
        ReaderBinding("help", "h"),
        ReaderBinding("help", "h", frozenset({"shift"})),
        ReaderBinding("help", "question"),
        ReaderBinding("help", "question", frozenset({"shift"})),
        ReaderBinding("escape", "escape"),
        ReaderBinding("escape", "escape", frozenset({"shift"})),
    ]
    return tuple(bindings)


def resolve_action(
    key: str,
    modifiers: frozenset[str],
    reading_direction: str,
    available: frozenset[str],
) -> str | None:
    for binding in reader_bindings(reading_direction):
        if (
            binding.key == key
            and binding.modifiers == modifiers
            and is_action_available(binding.action_id, available)
        ):
            return binding.action_id
    return None


def overlay_action_ids(available: frozenset[str], reading_direction: str) -> tuple[str, ...]:
    navigation = ("next", "previous", "forward_one", "back_one")
    if reading_direction != "rtl":
        navigation = ("previous", "next", "back_one", "forward_one")
    ids = [*navigation, "original", "settings", "fullscreen", "layout", "help"]
    ids.extend(action_id for action_id in ("bookmark", "bookmarks") if is_action_available(action_id, available))
    ids.append("pages")
    return tuple(ids)


def help_entries(reading_direction: str, available: frozenset[str]) -> tuple[ReaderHelpEntry, ...]:
    next_key, previous_key = _direction_keys(reading_direction)
    next_arrow = "←" if next_key == "left" else "→"
    previous_arrow = "←" if previous_key == "left" else "→"
    entries = [
        ReaderHelpEntry("next", "{keys}: 次へ", f"{next_arrow} / ↓ / Space"),
        ReaderHelpEntry("previous", "{keys}: 前へ", f"{previous_arrow} / ↑ / Backspace"),
        ReaderHelpEntry("forward_one", "{keys}: 1ページ進める", f"Shift+{next_arrow} / Shift+↓ / E"),
        ReaderHelpEntry("back_one", "{keys}: 1ページ戻す", f"Shift+{previous_arrow} / Shift+↑ / Q"),
        ReaderHelpEntry("fullscreen", "F: 全画面表示/解除"),
        ReaderHelpEntry("settings", "P: 右設定パネル表示/非表示"),
        ReaderHelpEntry("layout", "V: 見開き/単ページを切り替え"),
        ReaderHelpEntry("original", "O: 原画/補正版を切り替え"),
        ReaderHelpEntry(None, "0: 全体に合わせる / W: 幅に合わせる / 1: 実寸"),
        ReaderHelpEntry(None, "+ / -: 表示倍率を変更 / Ctrl/⌘+ホイール: 表示倍率を変更"),
        ReaderHelpEntry("bookmark", "B: しおり追加"),
        ReaderHelpEntry("bookmarks", "Shift+B: しおり一覧"),
        ReaderHelpEntry("pages", "T: ページ一覧"),
        ReaderHelpEntry(None, "画面左右クリック: 次へ/前へ（読書方向に連動）"),
        ReaderHelpEntry(None, "Shift+画面左右クリック: 1ページ進む/戻す"),
        ReaderHelpEntry(None, "画面中央クリック: 操作ペインを表示/非表示"),
        ReaderHelpEntry(None, "右クリック: 前へ"),
        ReaderHelpEntry("escape", "Esc: 操作ペインを閉じる / 全画面解除 / 本棚へ戻る"),
        ReaderHelpEntry("help", "H / ?: このヘルプを表示"),
    ]
    return tuple(entry for entry in entries if entry.action_id is None or is_action_available(entry.action_id, available))

