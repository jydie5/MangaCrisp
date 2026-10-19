"""Reusable controls for the reader's settings and full-screen overlay.

The widgets in this module deliberately keep state in Qt's normal button
properties.  The reader owns the signal connections and decides what a click
does; these classes only provide consistent visuals, accessibility metadata,
and hit areas.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

READER_STYLE_SHEET = """
QWidget#readerRoot QWidget#controls {
    background: #171d26;
    border-left: 1px solid #303946;
}
QWidget#readerRoot QWidget#simplePanel,
QWidget#readerRoot QWidget#simple_panel {
    background: transparent;
    border: 0;
}
QWidget#readerRoot QWidget#readingControlsOverlay {
    background: rgba(22, 28, 36, 225);
    border: 1px solid rgba(255, 255, 255, 68);
    border-radius: 16px;
}
QWidget#readerRoot QLabel {
    background: transparent;
    border: 0;
}
QWidget#readerRoot QPushButton {
    color: #eef5f3;
    background: #252c36;
    border: 1px solid #414b5c;
    border-radius: 8px;
    min-height: 32px;
    padding: 6px 12px;
}
QWidget#readerRoot QPushButton:hover {
    border-color: #66d9c4;
}
QWidget#readerRoot QPushButton:pressed {
    color: #66d9c4;
    background: #183d3b;
}
QWidget#readerRoot QPushButton:focus {
    border: 2px solid #66d9c4;
}
QWidget#readerRoot QPushButton:checked {
    color: #66d9c4;
    background: #183d3b;
    border-color: #66d9c4;
}
QWidget#readerRoot QPushButton#choiceButton,
QWidget#readerRoot QPushButton#shortcutButton {
    color: transparent;
}
/*
 * The generic button rule's padding contributes to its minimum height.  The
 * custom cards own their inner layout, so use a zero-padded box here and
 * reserve the border pixels in the content height.  This keeps the explicit
 * widget heights stable after a stylesheet is applied.
 */
QWidget#readerRoot QPushButton#choiceButton {
    min-height: 70px;
    max-height: 70px;
    padding: 0;
}
QWidget#readerRoot QPushButton#shortcutButton[compact="true"] {
    min-height: 38px;
    max-height: 38px;
    padding: 0;
}
QWidget#readerRoot QPushButton#shortcutButton[compact="false"] {
    min-height: 46px;
    max-height: 46px;
    padding: 0;
}
QWidget#readerRoot QPushButton#choiceButton QLabel#choiceTitle,
QWidget#readerRoot QPushButton#shortcutButton QLabel#shortcutTitle {
    color: #eef5f3;
    font-size: 14px;
    font-weight: 700;
}
QWidget#readerRoot QPushButton#choiceButton QLabel#choiceSubtitle {
    color: #aeb8c2;
    font-size: 11px;
    font-weight: 400;
}
QWidget#readerRoot QPushButton#shortcutButton QLabel#shortcutKeycap {
    color: #cbeee8;
    background: #183d3b;
    border: 1px solid #416f6a;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
}
QWidget#readerRoot QPushButton#shortcutButton[compact="true"] QLabel#shortcutTitle {
    font-size: 12px;
}
QWidget#readerRoot QPushButton#shortcutButton[compact="true"] QLabel#shortcutKeycap {
    font-size: 10px;
    padding: 1px 5px;
}
"""


def _make_mouse_transparent(label: QLabel) -> QLabel:
    """Keep decorative labels from stealing their parent button's hit area."""
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    return label


class _WrappedElidedLabel(QLabel):
    """Wrap short descriptions and elide text that needs more than two lines."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        self._full_text = text
        self._fitting_text = False
        super().__init__(text, parent)

    def setText(self, text: str) -> None:
        self._full_text = text
        super().setText(text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_text_to_width()

    def _fit_text_to_width(self) -> None:
        if self._fitting_text:
            return
        width = self.contentsRect().width()
        if width <= 0:
            return

        self._fitting_text = True
        try:
            # Restore the source text first so growing the card can remove a
            # previous elision.  Two lines fit inside the 72px choice card.
            QLabel.setText(self, self._full_text)
            two_line_height = self.fontMetrics().lineSpacing() * 2
            if self.heightForWidth(width) > two_line_height:
                QLabel.setText(
                    self,
                    self.fontMetrics().elidedText(
                        self._full_text,
                        Qt.TextElideMode.ElideRight,
                        width,
                    ),
                )
        finally:
            self._fitting_text = False


class ChoiceButton(QPushButton):
    """A checkable two-line quality choice card."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self.title = title
        self.subtitle = subtitle
        self.setObjectName("choiceButton")
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(title)
        self.setAccessibleDescription(subtitle)

        self.title_label = _make_mouse_transparent(QLabel(title, self))
        self.title_label.setObjectName("choiceTitle")
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.subtitle_label = _make_mouse_transparent(
            _WrappedElidedLabel(subtitle, self)
        )
        self.subtitle_label.setObjectName("choiceSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 8, 13, 8)
        layout.setSpacing(2)
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)


class ShortcutButton(QPushButton):
    """A button with a descriptive label and a visible keyboard keycap."""

    def __init__(
        self,
        title: str,
        shortcut: str,
        parent: QWidget | None = None,
        compact: bool = False,
    ) -> None:
        super().__init__(title, parent)
        self.title = title
        self.shortcut = shortcut
        self.compact = compact
        self.setObjectName("shortcutButton")
        self.setProperty("compact", compact)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(title)
        self.setAccessibleDescription(shortcut)

        self.title_label = _make_mouse_transparent(QLabel(title, self))
        self.title_label.setObjectName("shortcutTitle")
        self.keycap_label = _make_mouse_transparent(QLabel(shortcut, self))
        self.keycap_label.setObjectName("shortcutKeycap")
        layout = QHBoxLayout(self)
        if compact:
            layout.setContentsMargins(8, 2, 8, 2)
            layout.setSpacing(6)
        else:
            layout.setContentsMargins(12, 4, 12, 4)
            layout.setSpacing(10)
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.keycap_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Dynamic stylesheet properties are set after the widget is created,
        # so explicitly repolish the button when its parent already has the
        # reader stylesheet.  The second fixed-height call restores the
        # public widget height after QSS has adjusted the box metrics.
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
        self.setFixedHeight(40 if compact else 48)

    def minimumSizeHint(self) -> QSize:
        """Keep both the title and keycap in the button's minimum width."""
        style_hint = super().minimumSizeHint()
        layout = self.layout()
        layout_hint = layout.minimumSize() if layout is not None else QSize()
        return QSize(
            max(style_hint.width(), layout_hint.width()),
            max(style_hint.height(), layout_hint.height(), self.height()),
        )

    def sizeHint(self) -> QSize:
        """Report the child layout's natural width without forcing a width."""
        style_hint = super().sizeHint()
        layout = self.layout()
        layout_hint = layout.sizeHint() if layout is not None else QSize()
        return QSize(
            max(style_hint.width(), layout_hint.width()),
            max(style_hint.height(), layout_hint.height(), self.height()),
        )

    def set_title(self, title: str) -> None:
        self.title = title
        self.setText(title)
        self.title_label.setText(title)
        self.setAccessibleName(title)
        self.updateGeometry()


class OverlayPane(QWidget):
    """Semi-transparent reader controls pane that dismisses on blank left clicks."""

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("readingControlsOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#readingControlsOverlay {"
            " background: rgba(22, 28, 36, 225);"
            " border: 1px solid rgba(255, 255, 255, 68);"
            " border-radius: 16px;"
            "}"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            position = event.position().toPoint()
            if self.childAt(position) is None:
                self.dismissed.emit()
                event.accept()
                return
        super().mousePressEvent(event)


__all__ = ["READER_STYLE_SHEET", "ChoiceButton", "OverlayPane", "ShortcutButton"]
