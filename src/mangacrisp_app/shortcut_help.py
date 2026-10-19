"""Shared shortcut help with a modal backdrop that consumes dismissal clicks."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from mangacrisp_app.branding import PROJECT_URL, SUPPORT_URL
from mangacrisp_app.i18n import tr

HELP_STYLE_SHEET = """
QWidget#shortcutHelpCard {
    background: rgba(22, 30, 41, 248);
    border: 1px solid #415163;
    border-radius: 16px;
}
QDialog#shortcutHelpBackdrop QLabel {
    background: transparent;
    border: 0;
    color: #eef5f3;
    font-size: 14px;
}
QDialog#shortcutHelpBackdrop QLabel#helpTitle { font-size: 22px; font-weight: 700; }
QDialog#shortcutHelpBackdrop QLabel#helpHint { color: #aeb8c2; font-size: 12px; }
QDialog#shortcutHelpBackdrop QLabel#helpKey {
    color: #bceee3;
    background: #183d3b;
    border: 1px solid #416f6a;
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 12px;
    font-weight: 600;
}
QDialog#shortcutHelpBackdrop QScrollArea,
QDialog#shortcutHelpBackdrop QWidget#helpRows { background: transparent; border: 0; }
QDialog#shortcutHelpBackdrop QPushButton {
    background: #252c36;
    color: #eef5f3;
    border: 1px solid #414b5c;
    border-radius: 8px;
    min-height: 34px;
    padding: 4px 14px;
    font-size: 14px;
}
QDialog#shortcutHelpBackdrop QPushButton:hover,
QDialog#shortcutHelpBackdrop QPushButton:focus { border: 2px solid #66d9c4; }
QDialog#shortcutHelpBackdrop QPushButton:pressed { background: #183d3b; }
QDialog#shortcutHelpBackdrop QScrollBar:vertical { background: #151f2e; width: 10px; }
QDialog#shortcutHelpBackdrop QScrollBar::handle:vertical {
    background: #516172; border-radius: 5px; min-height: 30px;
}
QDialog#shortcutHelpBackdrop QScrollBar::add-line:vertical,
QDialog#shortcutHelpBackdrop QScrollBar::sub-line:vertical { height: 0; }
"""


class ShortcutHelpDialog(QDialog):
    """Cover the host window, keeping outside clicks away from the reader."""

    def __init__(self, parent: QWidget, shortcuts_text: str) -> None:
        host = parent.window()
        super().__init__(host, Qt.Dialog | Qt.FramelessWindowHint)
        self.setObjectName("shortcutHelpBackdrop")
        self.setWindowTitle(tr("ショートカット"))
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setModal(True)
        self.setStyleSheet(HELP_STYLE_SHEET)
        self._outside_press = None
        self._row_count = len(shortcuts_text.splitlines())
        origin = host.mapToGlobal(QPoint(0, 0))
        self.setGeometry(origin.x(), origin.y(), host.width(), host.height())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setAlignment(Qt.AlignCenter)
        self.card = QWidget(self)
        self.card.setObjectName("shortcutHelpCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(self.card)
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel(tr("操作一覧"), self.card)
        title.setObjectName("helpTitle")
        header.addWidget(title, 1)
        self.close_button = QPushButton(tr("閉じる") + "  Esc", self.card)
        self.close_button.setAccessibleName(tr("閉じる"))
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.clicked.connect(self.reject)
        header.addWidget(self.close_button)
        layout.addLayout(header)

        self.scroll = QScrollArea(self.card)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rows = QWidget(self.scroll)
        rows.setObjectName("helpRows")
        grid = QGridLayout(rows)
        grid.setContentsMargins(0, 0, 12, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        for row, line in enumerate(shortcuts_text.splitlines()):
            key, separator, description = line.partition(":")
            if not separator:
                key, description = "", line
            key_label = QLabel(key.strip(), rows)
            key_label.setObjectName("helpKey")
            key_label.setTextFormat(Qt.PlainText)
            key_label.setWordWrap(True)
            key_label.setFixedWidth(196)
            key_label.setAlignment(Qt.AlignCenter)
            description_label = QLabel(description.strip(), rows)
            description_label.setWordWrap(True)
            description_label.setTextFormat(Qt.PlainText)
            grid.addWidget(key_label, row, 0)
            grid.addWidget(description_label, row, 1)
        grid.setRowStretch(self._row_count, 1)
        self.scroll.setWidget(rows)
        layout.addWidget(self.scroll, 1)

        self.project_links = QLabel(self.card)
        self.project_links.setWordWrap(True)
        self.project_links.setText(
            f'<a style="color:#66d9c4" href="{PROJECT_URL}">{escape(tr("ソースコード・不具合報告"))}</a>'
            " &nbsp; · &nbsp; "
            f'<a style="color:#66d9c4" href="{SUPPORT_URL}">{escape(tr("開発を支援（任意）"))}</a>'
        )
        self.project_links.setOpenExternalLinks(True)
        self.project_links.setTextInteractionFlags(Qt.TextBrowserInteraction)
        layout.addWidget(self.project_links)
        hint = QLabel(tr("ペインの外をクリックして閉じる"), self.card)
        hint.setObjectName("helpHint")
        layout.addWidget(hint)
        self._fit_card()
        self.close_button.setFocus(Qt.OtherFocusReason)

    def _fit_card(self) -> None:
        if not hasattr(self, "card"):
            return
        width = min(800, max(1, self.width() - 40))
        height = min(210 + self._row_count * 46, 800, max(1, self.height() - 40))
        self.card.setFixedSize(width, height)

    def paintEvent(self, event) -> None:
        # A translucent top-level QDialog does not reliably paint a QSS
        # background. Nonzero alpha also keeps the backdrop hit-testable on macOS.
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(7, 12, 19, 155))
        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_card()

    def mousePressEvent(self, event) -> None:
        self._outside_press = None
        if event.button() in {
            Qt.LeftButton,
            Qt.RightButton,
        } and not self.card.geometry().contains(event.position().toPoint()):
            self._outside_press = event.button()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        dismiss = (
            self._outside_press == event.button()
            and not self.card.geometry().contains(event.position().toPoint())
        )
        self._outside_press = None
        event.accept()
        # Dismiss only after the release, so the click cannot reach the page
        # or a bookshelf item exposed by hiding the modal window.
        if dismiss:
            self.reject()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            event.accept()
            self.reject()
            return
        super().keyPressEvent(event)
        event.accept()
