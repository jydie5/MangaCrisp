from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QGridLayout, QPushButton, QVBoxLayout, QWidget

from mangacrisp_app.reader_widgets import (
    READER_STYLE_SHEET,
    ChoiceButton,
    OverlayPane,
    ShortcutButton,
)


def test_reader_style_sheet_is_scoped_to_reader_widgets() -> None:
    assert "QWidget#readerRoot" in READER_STYLE_SHEET
    assert "#controls" in READER_STYLE_SHEET
    assert "#simplePanel" in READER_STYLE_SHEET
    assert "#readingControlsOverlay" in READER_STYLE_SHEET
    assert "QWidget {" not in READER_STYLE_SHEET


def test_choice_button_is_a_full_size_accessible_card(qapp) -> None:
    root = QWidget()
    root.setObjectName("readerRoot")
    root.setStyleSheet(READER_STYLE_SHEET)
    button = ChoiceButton("自然", "se / noise 0", root)

    assert button.isCheckable()
    assert button.text() == "自然"
    assert button.accessibleName() == "自然"
    assert button.accessibleDescription() == "se / noise 0"
    assert button.height() == 72
    assert button.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert button.title_label.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents
    )
    assert button.subtitle_label.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents
    )

    button.click()
    assert button.isChecked()

    root.deleteLater()
    qapp.processEvents()


def test_choice_subtitles_fit_two_column_cards(qapp) -> None:
    root = QWidget()
    root.setObjectName("readerRoot")
    root.setStyleSheet(READER_STYLE_SHEET)
    root.resize(304, 200)
    layout = QGridLayout(root)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    buttons = (
        ChoiceButton("Natural", "Natural Lines and Tones", root),
        ChoiceButton(
            "Cleaning",
            "pro/noise 3. Prioritizes line and texture quality over processing time.",
            root,
        ),
    )
    for column, button in enumerate(buttons):
        layout.addWidget(button, 0, column)

    root.show()
    qapp.processEvents()
    for button in buttons:
        subtitle = button.subtitle_label
        assert button.width() == 148
        assert subtitle.geometry().right() < button.width()
        assert subtitle.geometry().bottom() < button.height()
        assert subtitle.heightForWidth(subtitle.width()) <= subtitle.height()

    # Native fonts have different metrics. A narrow card may elide even this
    # short description; its complete accessible text must still be retained.
    assert buttons[0].accessibleDescription() == "Natural Lines and Tones"
    assert buttons[0].subtitle_label.text()
    assert "…" in buttons[1].subtitle_label.text()
    assert buttons[1].subtitle == (
        "pro/noise 3. Prioritizes line and texture quality over processing time."
    )

    # Growing a card must restore text that was elided at the narrow width.
    root.resize(800, 200)
    qapp.processEvents()
    assert buttons[0].subtitle_label.text() == "Natural Lines and Tones"

    root.close()
    root.deleteLater()
    qapp.processEvents()


def test_shortcut_button_has_compact_and_normal_sizes(qapp) -> None:
    root = QWidget()
    root.setObjectName("readerRoot")
    root.setStyleSheet(READER_STYLE_SHEET)
    compact = ShortcutButton("次へ", "←", root, compact=True)
    normal = ShortcutButton("原画比較", "O", root)

    assert compact.height() == 40
    assert normal.height() == 48
    assert compact.text() == "次へ"
    assert compact.accessibleName() == "次へ"
    assert compact.accessibleDescription() == "←"
    assert compact.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert compact.keycap_label.text() == "←"
    assert compact.keycap_label.testAttribute(
        Qt.WidgetAttribute.WA_TransparentForMouseEvents
    )

    root.deleteLater()
    qapp.processEvents()


def test_shortcut_button_hints_include_both_child_labels(qapp) -> None:
    root = QWidget()
    root.setObjectName("readerRoot")
    root.setStyleSheet(READER_STYLE_SHEET)
    button = ShortcutButton(
        "Long English Action Label",
        "Shift+ArrowLeft",
        root,
        compact=True,
    )

    # The parent uses this width when deciding whether to reflow the action
    # bar.  It must include the keycap as well as the translated title.
    layout = button.layout()
    assert layout is not None
    assert button.minimumSizeHint().width() >= layout.minimumSize().width()
    assert button.sizeHint().width() >= layout.sizeHint().width()
    assert button.minimumSizeHint().height() >= button.height()

    button.set_title("さらに長い English command title")
    assert button.title_label.text() == "さらに長い English command title"
    assert button.accessibleName() == "さらに長い English command title"
    assert button.sizeHint().width() >= button.layout().sizeHint().width()

    root.deleteLater()
    qapp.processEvents()


def test_reader_button_heights_survive_stylesheet_layout(qapp) -> None:
    root = QWidget()
    root.setObjectName("readerRoot")
    root.setStyleSheet(READER_STYLE_SHEET)
    layout = QVBoxLayout(root)
    buttons = (
        ChoiceButton("自然", "se / noise 0", root),
        ShortcutButton("次へ", "←", root, compact=True),
        ShortcutButton("原画比較", "O", root),
    )
    for button in buttons:
        layout.addWidget(button)

    root.show()
    qapp.processEvents()
    assert [button.height() for button in buttons] == [72, 40, 48]
    assert [button.minimumHeight() for button in buttons] == [72, 40, 48]
    assert [button.maximumHeight() for button in buttons] == [72, 40, 48]

    root.close()
    root.deleteLater()
    qapp.processEvents()


def test_overlay_dismisses_only_on_blank_left_click(qapp) -> None:
    root = QWidget()
    root.resize(320, 220)
    overlay = OverlayPane(root)
    overlay.setGeometry(0, 0, 320, 220)
    child = QPushButton("操作", overlay)
    child.setGeometry(20, 20, 100, 40)
    dismissed: list[bool] = []
    overlay.dismissed.connect(lambda: dismissed.append(True))
    root.show()
    overlay.show()
    qapp.processEvents()

    QTest.mouseClick(
        overlay, Qt.MouseButton.LeftButton, pos=overlay.rect().bottomRight()
    )
    assert dismissed == [True]
    QTest.mouseClick(child, Qt.MouseButton.LeftButton)
    assert dismissed == [True]
    QTest.mouseClick(overlay, Qt.MouseButton.RightButton, pos=overlay.rect().topRight())
    assert dismissed == [True]

    root.close()
    root.deleteLater()
    qapp.processEvents()
