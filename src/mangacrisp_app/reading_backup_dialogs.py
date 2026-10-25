"""Bookshelf entry points for small, same-library reading-record backups."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from mangacrisp_app.i18n import tr
from mangacrisp_app.library import LibraryService
from mangacrisp_app.reading_backup import (
    export_reading_backup,
    load_reading_backup,
    preview_reading_restore,
    restore_reading_backup,
)


def _message(parent: QWidget, title: str, text: str, detail: str = "") -> QMessageBox:
    dialog = QMessageBox(parent)
    dialog.setObjectName("readingRecordsDialog")
    dialog.setStyleSheet("""
        QMessageBox#readingRecordsDialog { background: #151f2e; }
        QMessageBox#readingRecordsDialog QLabel { color: #eef5f3; font-size: 14px; }
        QMessageBox#readingRecordsDialog QPushButton {
            background: #1d293a; color: #eef5f3; border: 1px solid #3b4d62;
            border-radius: 8px; min-height: 32px; padding: 2px 16px;
        }
        QMessageBox#readingRecordsDialog QPushButton:hover,
        QMessageBox#readingRecordsDialog QPushButton:focus { border: 2px solid #66d9c4; }
    """)
    dialog.setWindowTitle(title)
    dialog.setTextFormat(Qt.PlainText)
    dialog.setText(text)
    if detail:
        dialog.setInformativeText(detail)
    return dialog


def export_records(parent: QWidget, library: LibraryService) -> bool:
    filename, _filter = QFileDialog.getSaveFileName(
        parent,
        tr("読書記録を書き出す"),
        "MangaCrisp-reading-records.mangacrisp.json",
        tr("読書記録 (*.json)"),
    )
    if not filename:
        return False
    destination = Path(filename)
    if not destination.suffix:
        destination = destination.with_suffix(".mangacrisp.json")
    try:
        export_reading_backup(library, destination)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        dialog = _message(parent, tr("読書記録を書き出す"), tr("読書記録を書き出せませんでした。"), str(exc))
        dialog.setIcon(QMessageBox.Warning)
        dialog.exec()
        return False
    dialog = _message(
        parent,
        tr("読書記録を書き出す"),
        tr("読書記録を書き出しました。"),
        tr("同じ本棚の読書位置・状態・表示設定・しおりを復元できます。漫画本体や全体設定は含みません。書名としおりのメモは含まれます。"),
    )
    dialog.setIcon(QMessageBox.Information)
    dialog.exec()
    return True


def restore_records(parent: QWidget, library: LibraryService) -> bool:
    filename, _filter = QFileDialog.getOpenFileName(
        parent, tr("読書記録を復元する"), "", tr("読書記録 (*.json)")
    )
    if not filename:
        return False
    try:
        document = load_reading_backup(Path(filename))
        plan = preview_reading_restore(library, document)
        summary = tr(
            "復元対象: {matched}冊\n対象の本なし: {missing}冊\n互換性なし: {incompatible}冊\n追加するしおり: {bookmarks}件",
            matched=plan.matched_count,
            missing=plan.missing_count,
            incompatible=plan.incompatible_count,
            bookmarks=plan.bookmarks_added,
        )
        if not plan.matched_count:
            dialog = _message(parent, tr("読書記録を復元する"), tr("この本棚に復元できる記録がありません。"), summary)
            dialog.setIcon(QMessageBox.Information)
            dialog.exec()
            return False
        dialog = _message(
            parent,
            tr("読書記録を復元する"),
            tr("一致した本の読書記録を、保存した内容へ戻しますか？"),
            summary + "\n\n" + tr("現在の読書位置・読書状態・本ごとの表示設定を置き換えます。既存しおりのラベル・メモは残し、未登録のページだけ追加します。漫画本体と全体設定は変更しません。"),
        )
        dialog.setIcon(QMessageBox.Question)
        dialog.setStandardButtons(QMessageBox.Cancel)
        restore_button = dialog.addButton(tr("復元する"), QMessageBox.AcceptRole)
        dialog.setDefaultButton(QMessageBox.Cancel)
        dialog.exec()
        if dialog.clickedButton() is not restore_button:
            return False
        restore_reading_backup(library, plan)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        dialog = _message(parent, tr("読書記録を復元する"), tr("読書記録を復元できませんでした。"), str(exc))
        dialog.setIcon(QMessageBox.Warning)
        dialog.exec()
        return False
    dialog = _message(parent, tr("読書記録を復元する"), tr("読書記録を復元しました。"), summary)
    dialog.setIcon(QMessageBox.Information)
    dialog.exec()
    return True
