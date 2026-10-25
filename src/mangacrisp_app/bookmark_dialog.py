"""Modal bookmark list used by the reader controls."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from html import escape

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mangacrisp_app.i18n import tr
from mangacrisp_app.library import Bookmark, normalize_bookmark_text

BOOKMARK_VALIDATION_MESSAGES = {
    "bookmark label must be text": "しおりのラベルは文字で入力してください。",
    "bookmark label cannot be empty": "しおりのラベルを入力してください。",
    "bookmark label is too long": "しおりのラベルは1024文字以内にしてください。",
    "bookmark note must be text": "しおりのメモは文字で入力してください。",
    "bookmark note is too long": "しおりのメモは4096文字以内にしてください。",
}

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
QDialog#bookmarkEditor {
    background: #161e29;
    color: #eef5f3;
}
QDialog#bookmarkEditor QLabel {
    color: #eef5f3;
    font-size: 14px;
}
QDialog#bookmarkEditor QLineEdit,
QDialog#bookmarkEditor QPlainTextEdit {
    background: #101a27;
    color: #eef5f3;
    border: 1px solid #415163;
    border-radius: 8px;
    padding: 8px;
}
QDialog#bookmarkEditor QLineEdit:focus,
QDialog#bookmarkEditor QPlainTextEdit:focus {
    border: 2px solid #66d9c4;
}
QDialog#bookmarkEditor QPushButton {
    background: #252c36;
    color: #eef5f3;
    border: 1px solid #414b5c;
    border-radius: 8px;
    min-height: 34px;
    padding: 4px 14px;
}
QDialog#bookmarkEditor QPushButton:hover,
QDialog#bookmarkEditor QPushButton:focus {
    border: 2px solid #66d9c4;
}
QDialog#bookmarkEditor QLabel#bookmarkEditorStatus {
    color: #f0b36b;
    font-size: 12px;
}
"""


class BookmarkEditorDialog(QDialog):
    """Edit one bookmark while retaining input after a storage failure."""

    def __init__(
        self,
        parent: QWidget,
        bookmark: Bookmark,
        save_callback: Callable[[str, str, str | None], Bookmark | None],
    ) -> None:
        super().__init__(parent, Qt.Dialog)
        self.setObjectName("bookmarkEditor")
        self.setWindowTitle(tr("しおりを編集"))
        self.setModal(True)
        self.setStyleSheet(BOOKMARK_STYLE_SHEET)
        self.bookmark = bookmark
        self.save_callback = save_callback
        self.updated_bookmark: Bookmark | None = None
        self.resize(520, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        page_label = QLabel(tr("ページ: {page}", page=bookmark.page_index + 1), self)
        layout.addWidget(page_label)
        label_caption = QLabel(tr("ラベル"), self)
        layout.addWidget(label_caption)
        self.label_edit = QLineEdit(bookmark.label, self)
        self.label_edit.setAccessibleName(tr("しおりのラベル"))
        self.label_edit.textChanged.connect(self._clear_status)
        layout.addWidget(self.label_edit)
        note_caption = QLabel(tr("メモ"), self)
        layout.addWidget(note_caption)
        self.note_edit = QPlainTextEdit(bookmark.note or "", self)
        self.note_edit.setAccessibleName(tr("しおりのメモ"))
        self.note_edit.setPlaceholderText(tr("メモを追加（任意）"))
        self.note_edit.textChanged.connect(self._clear_status)
        layout.addWidget(self.note_edit, 1)
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("bookmarkEditorStatus")
        self.status_label.setTextFormat(Qt.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton(tr("キャンセル"), self)
        self.cancel_button.clicked.connect(self.reject)
        actions.addWidget(self.cancel_button)
        self.save_button = QPushButton(tr("保存"), self)
        self.save_button.setDefault(True)
        self.cancel_button.setAutoDefault(False)
        self.save_button.clicked.connect(self._save)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.label_edit.setFocus(Qt.OtherFocusReason)

    def _clear_status(self) -> None:
        self.status_label.clear()

    def _save(self) -> None:
        try:
            label, note = normalize_bookmark_text(self.label_edit.text(), self.note_edit.toPlainText())
        except (TypeError, ValueError) as exc:
            self.status_label.setText(tr("しおりを保存できません: {error}", error=tr(BOOKMARK_VALIDATION_MESSAGES.get(str(exc), "しおりを保存できませんでした。"))))
            return
        try:
            updated = self.save_callback(self.bookmark.id, label, note)
        except Exception:  # noqa: BLE001 - keep user input at a callback boundary.
            updated = None
        if not isinstance(updated, Bookmark) or updated.id != self.bookmark.id:
            self.status_label.setText(tr("しおりを保存できませんでした。"))
            return
        self.updated_bookmark = updated
        self.accept()


class BookmarkDialog(QDialog):
    """Show, select, and delete bookmarks without exposing the reader behind it."""

    def __init__(
        self,
        parent: QWidget,
        bookmarks: Sequence[Bookmark],
        page_count: int,
        delete_callback: Callable[[str], bool] | None = None,
        edit_callback: Callable[[str, str, str | None], Bookmark | None] | None = None,
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
        self.edit_callback = edit_callback
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
        self.edit_button = QPushButton(tr("編集"), self.card)
        self.edit_button.setAccessibleName(tr("しおりを編集"))
        self.edit_button.clicked.connect(self._edit_selected)
        self.edit_button.setVisible(self.edit_callback is not None)
        actions.addWidget(self.edit_button)
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
            if bookmark.note:
                note_preview = " ".join(bookmark.note.splitlines()).strip()
                if len(note_preview) > 120:
                    note_preview = note_preview[:119] + "…"
                if note_preview:
                    label += f"\n{note_preview}"
            if not valid:
                label += f"  ({tr('無効')})"
            item = QListWidgetItem(label, self.list_widget)
            item.setData(Qt.UserRole, bookmark.id)
            item.setData(Qt.UserRole + 1, bookmark.page_index)
            tooltip = f"{page_label}  {bookmark.label}"
            if not valid:
                tooltip += "\n\n" + tr("このしおりのページは無効です。削除できます。")
            if bookmark.note:
                tooltip += f"\n\n{bookmark.note}"
            item.setToolTip("<qt>" + escape(tooltip).replace("\n", "<br/>") + "</qt>")
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
        self.edit_button.setEnabled(bookmark is not None and self.edit_callback is not None)
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
        except Exception:  # noqa: BLE001 - surface a callback failure in the dialog.
            deleted = False
        if deleted is not True:
            self.status_label.setText(tr("しおりを削除できませんでした。"))
            return
        self.bookmarks = [candidate for candidate in self.bookmarks if candidate.id != bookmark.id]
        self.status_label.clear()
        self._populate()

    def _edit_selected(self) -> None:
        bookmark = self._selected_bookmark()
        if bookmark is None or self.edit_callback is None:
            return
        editor = BookmarkEditorDialog(self, bookmark, self.edit_callback)
        try:
            if editor.exec() != QDialog.DialogCode.Accepted or editor.updated_bookmark is None:
                return
            self.bookmarks = [
                editor.updated_bookmark if candidate.id == bookmark.id else candidate
                for candidate in self.bookmarks
            ]
            self.status_label.clear()
            self._populate()
            for row in range(self.list_widget.count()):
                if self.list_widget.item(row).data(Qt.UserRole) == bookmark.id:
                    self.list_widget.setCurrentRow(row)
                    break
        finally:
            editor.deleteLater()

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


__all__ = ["BOOKMARK_STYLE_SHEET", "BookmarkDialog", "BookmarkEditorDialog"]
