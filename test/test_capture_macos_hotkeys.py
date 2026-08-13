from mangacrisp_app.platform.capture_macos import (
    CARBON_OPTION,
    default_hotkey_bindings,
    hotkey_presets,
)


def test_default_capture_hotkeys_use_two_keys() -> None:
    bindings = default_hotkey_bindings()

    assert bindings.capture.label == "Option+C"
    assert bindings.capture.modifiers == CARBON_OPTION
    assert bindings.undo.label == "Option+Z"
    assert bindings.undo.modifiers == CARBON_OPTION


def test_legacy_capture_hotkeys_remain_selectable() -> None:
    labels = {(item.capture.label, item.undo.label) for item in hotkey_presets()}

    assert ("Command+Option+C", "Command+Option+Z") in labels
    assert ("Control+Return", "Control+Delete") in labels
