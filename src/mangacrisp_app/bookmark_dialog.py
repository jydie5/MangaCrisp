"""Modal bookmark list used by the reader controls."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mangacrisp_app.i18n import tr
from mangacrisp_app.library import Bookmark

BOOKMARK_STYLE_SHEET = """
QWidget#bookmarkCard {
    background: rgba(22, 30, 41, 248);
    border: 1px solid #415163;
    border-radius: 16px;
}
QDialog#bookmarkBackdrop QLabel {
    background: transparent;
    border: 0;
    color: #eef5f3;
    font-size: 14px;
}
QDialog#bookmarkBackdrop QLabel#bookmarkTitle {
    font-size: 22px;
    font-weight: 700;
}
QDialog#bookmarkBackdrop QLabel#bookmarkHint,
QDialog#bookmarkBackdrop QLabel#bookmarkStatus {
    color: #aeb8c2;
    font-size: 12px;
}
QDialog#bookmarkBackdrop QListWidget {
    background: #101a27;
    color: #eef5f3;
    border: 1px solid #415163;
    border-radius: 8px;
    outline: 0;
    padding: 4px;
}
QDialog#bookmarkBackdrop QListWidget::item {
    padding: 10px 12px;
    border-radius: 6px;
}
QDialog#bookmarkBackdrop QListWidget::item:selected {
    color: #bceee3;
    background: #183d3b;
    border: 1px solid #416f6a;
}
QDialog#bookmarkBackdrop QPushButton {
    background: #252c36;
    color: #eef5f3;
    border: 1px solid #414b5c;
    border-radius: 8px;
    min-height: 34px;
    padding: 4px 14px;
    font-size: 14px;
}
QDialog#bookmarkBackdrop QPushButton:hover,
QDialog#bookmarkBackdrop QPushButton:focus {
    border: 2px solid #66d9c4;
}
QDialog#bookmarkBackdrop QPushButton:pressed {
    background: #183d3b;
}
QDialog#bookmarkBackdrop QPushButton:disabled {
    color: #687482;
    background: #1b222c;
    border-color: #303946;
}
"""


class BookmarkDialog(QDialog):
    """Show, select, and delete bookmarks without exposing the reader behind it."""

    def __init__(
        self,
        parent: QWidget,
        bookmarks: Sequence[Bookmark],
        page_count: int,
        delete_callback: Callable[[str], bool] | None = None,
    ) -> None:
        host = parent.window()
        super().__init__(host, Qt.Dialog | Qt.FramelessWindowHint)
        self.setObjectName("bookmarkBackdrop")
        self.setWindowTitle(tr("しおり一覧"))
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setModal(True)
        self.setStyleSheet(BOOKMARK_STYLE_SHEET)
        self._outside_press = None
        self.page_count = max(0, page_count)
        self.delete_callback = delete_callback
        self.bookmarks = list(bookmarks)
        self.selected_page_index: int | None = None

        origin = host.mapToGlobal(QPoint(0, 0))
        self.setGeometry(origin.x(), origin.y(), host.width(), host.height())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setAlignment(Qt.AlignCenter)
        self.card = QWidget(self)
        self.card.setObjectName("bookmarkCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(self.card)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel(tr("しおり一覧"), self.card)
        title.setObjectName("bookmarkTitle")
        header.addWidget(title, 1)
        self.close_button = QPushButton(tr("閉じる") + "  Esc", self.card)
        self.close_button.setAccessibleName(tr("閉じる"))
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.clicked.connect(self.reject)
        header.addWidget(self.close_button)
        layout.addLayout(header)

        self.list_widget = QListWidget(self.card)
        self.list_widget.setAccessibleName(tr("しおり一覧"))
        self.list_widget.setMinimumHeight(220)
        self.list_widget.itemSelectionChanged.connect(self._update_selection_state)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_selected())
        layout.addWidget(self.list_widget, 1)

        self.empty_label = QLabel(tr("しおりはありません。"), self.card)
        self.empty_label.setObjectName("bookmarkStatus")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        self.status_label = QLabel(self.card)
        self.status_label.setObjectName("bookmarkStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.go_button = QPushButton(tr("移動"), self.card)
        self.go_button.setAccessibleName(tr("しおりへ移動"))
        self.go_button.setToolTip(tr("選択したしおりへ移動"))
        self.go_button.clicked.connect(self._accept_selected)
        actions.addWidget(self.go_button)
        self.delete_button = QPushButton(tr("削除"), self.card)
        self.delete_button.setAccessibleName(tr("しおりを削除"))
        self.delete_button.clicked.connect(self._delete_selected)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)
        hint = QLabel(tr("ペインの外をクリックして閉じる"), self.card)
        hint.setObjectName("bookmarkHint")
        layout.addWidget(hint)

        self._populate()
        self._fit_card()
        self.close_button.setFocus(Qt.OtherFocusReason)

    def _populate(self) -> None:
        self.list_widget.clear()
        for bookmark in self.bookmarks:
            valid = 0 <= bookmark.page_index < self.page_count
            page_label = f"p.{bookmark.page_index + 1}"
            label = page_label if bookmark.label == page_label else f"{page_label}  {bookmark.label}"
            if not valid:
                label += f"  ({tr('無効')})"
            item = QListWidgetItem(label, self.list_widget)
            item.setData(Qt.UserRole, bookmark.id)
            item.setData(Qt.UserRole + 1, bookmark.page_index)
            item.setToolTip(
                tr("このしおりのページは無効です。削除できます。")
                if not valid
                else label
            )
            if not valid:
                item.setForeground(QColor("#8c98a5"))
        self.empty_label.setVisible(not self.bookmarks)
        self.list_widget.setVisible(bool(self.bookmarks))
        if self.bookmarks:
            self.list_widget.setCurrentRow(0)
        else:
            self.status_label.clear()
        self._update_selection_state()

    def _selected_bookmark(self) -> Bookmark | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        bookmark_id = item.data(Qt.UserRole)
        return next((bookmark for bookmark in self.bookmarks if bookmark.id == bookmark_id), None)

    def _update_selection_state(self) -> None:
        bookmark = self._selected_bookmark()
        valid = bookmark is not None and 0 <= bookmark.page_index < self.page_count
        self.go_button.setEnabled(valid)
        self.delete_button.setEnabled(bookmark is not None and self.delete_callback is not None)
        if bookmark is not None and not valid:
            self.status_label.setText(tr("このしおりのページは無効です。削除できます。"))
        else:
            self.status_label.clear()

    def _accept_selected(self) -> None:
        bookmark = self._selected_bookmark()
        if bookmark is None or not (0 <= bookmark.page_index < self.page_count):
            return
        self.selected_page_index = bookmark.page_index
        self.accept()

    def _delete_selected(self) -> None:
        bookmark = self._selected_bookmark()
        if bookmark is None or self.delete_callback is None:
            return
        try:
            deleted = self.delete_callback(bookmark.id)
        except Exception:  # noqa: BLE001 - deletion callback is a UI/application boundary.
            deleted = False
        if deleted is not True:
            self.status_label.setText(tr("しおりを削除できませんでした。"))
            return
        self.bookmarks = [candidate for candidate in self.bookmarks if candidate.id != bookmark.id]
        self.status_label.clear()
        self._populate()

    def _fit_card(self) -> None:
        width = min(720, max(1, self.width() - 40))
        height = min(560, max(1, self.height() - 40))
        self.card.setFixedSize(width, height)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(7, 12, 19, 155))
        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_card()

    def mousePressEvent(self, event) -> None:
        self._outside_press = None
        if event.button() in {Qt.LeftButton, Qt.RightButton} and not self.card.geometry().contains(event.position().toPoint()):
            self._outside_press = event.button()
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        dismiss = (
            self._outside_press == event.button()
            and not self.card.geometry().contains(event.position().toPoint())
        )
        self._outside_press = None
        event.accept()
        if dismiss:
            self.reject()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            event.accept()
            self.reject()
            return
        super().keyPressEvent(event)
        event.accept()


__all__ = ["BOOKMARK_STYLE_SHEET", "BookmarkDialog"]
