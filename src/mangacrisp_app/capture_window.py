from __future__ import annotations

import shutil
import threading
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mangacrisp_app.capture.coordinator import CaptureCoordinator, CaptureQueueFullError
from mangacrisp_app.capture.models import CapturePage
from mangacrisp_app.capture.session import CaptureSession
from mangacrisp_app.i18n import tr
from mangacrisp_app.platform import (
    create_screen_capture_backend,
    open_directory,
    screen_capture_hotkey_presets,
)
from mangacrisp_app.platform.capture_base import (
    CaptureDisplay,
    CaptureRect,
    PermissionState,
)
from mangacrisp_app.region_selector import RegionSelector

CAPTURE_DEBOUNCE_SECONDS = 0.15
CAPTURE_FEEDBACK_SIZE = QSize(190, 52)
CAPTURE_FEEDBACK_MARGIN = 12


def capture_feedback_position(
    display: CaptureDisplay,
    region: CaptureRect,
    size: QSize = CAPTURE_FEEDBACK_SIZE,
) -> QPoint | None:
    """Return a feedback position that does not overlap the capture region."""
    display_left = display.x
    display_top = display.y
    display_right = display.x + display.width
    display_bottom = display.y + display.height
    width = size.width()
    height = size.height()
    preferred_x = min(max(region.x + region.width - width, display_left), display_right - width)
    preferred_y = min(max(region.y, display_top), display_bottom - height)
    candidates = (
        QPoint(preferred_x, region.y - height - CAPTURE_FEEDBACK_MARGIN),
        QPoint(preferred_x, region.y + region.height + CAPTURE_FEEDBACK_MARGIN),
        QPoint(region.x + region.width + CAPTURE_FEEDBACK_MARGIN, preferred_y),
        QPoint(region.x - width - CAPTURE_FEEDBACK_MARGIN, preferred_y),
    )
    for point in candidates:
        if (
            point.x() >= display_left
            and point.y() >= display_top
            and point.x() + width <= display_right
            and point.y() + height <= display_bottom
        ):
            return point
    return None


class CaptureFeedback(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(CAPTURE_FEEDBACK_SIZE)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "background: rgba(20, 20, 20, 225); color: white; "
            "border: 1px solid rgba(255, 255, 255, 70); border-radius: 6px; "
            "font-size: 15px; font-weight: 600; padding: 7px 10px;"
        )
        layout.addWidget(self.label)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_message(
        self,
        message: str,
        *,
        display: CaptureDisplay | None,
        region: CaptureRect | None,
    ) -> None:
        if display is None or region is None:
            return
        position = capture_feedback_position(display, region, self.size())
        if position is None:
            return
        self.label.setText(message)
        self.move(position)
        self.show()
        self.raise_()
        self._hide_timer.start(900)


class CaptureSignals(QObject):
    request_capture = Signal()
    request_undo = Signal()
    page_saved = Signal(object, object)
    package_done = Signal(object, object)
    close_ready = Signal()


class CaptureWindow(QMainWindow):
    def __init__(
        self,
        *,
        on_import: Callable[[Path], None] | None = None,
        backend=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.backend = backend or create_screen_capture_backend()
        self.on_import = on_import
        self.displays: list[CaptureDisplay] = []
        self.region: CaptureRect | None = None
        self.session: CaptureSession | None = None
        self.coordinator: CaptureCoordinator | None = None
        self.running = False
        self.retake_position: int | None = None
        self.last_capture_started = 0.0
        self._reloading_pages = False
        self._closing = False
        self.signals = CaptureSignals()
        self.signals.request_capture.connect(self.capture_requested)
        self.signals.request_undo.connect(self.undo_last)
        self.signals.page_saved.connect(self.on_page_saved)
        self.signals.package_done.connect(self.on_package_done)
        self.signals.close_ready.connect(self.close)
        self.capture_feedback = CaptureFeedback()
        self.setWindowTitle(tr("MangaCrisp 連番キャプチャ"))
        self.setMinimumSize(760, 620)
        self.resize(860, 720)
        self.setStyleSheet(
            "QMainWindow, QWidget { background: #151515; color: #eeeeee; font-size: 15px; } "
            "QLineEdit, QComboBox, QSpinBox, QListWidget { background: #0f0f0f; border: 1px solid #3a3a3a; "
            "padding: 5px; } QPushButton { min-height: 30px; padding: 5px 10px; } "
            "QLabel#muted { color: #b8b8b8; font-size: 13px; }"
        )
        self._build_ui()
        self.refresh_displays()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(tr("連番スクリーンキャプチャ"), root)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)
        description = QLabel(
            tr("権利を持つ画面を手動で1枚ずつPNG保存し、CBZまたはZIPにまとめます。"),
            root,
        )
        description.setObjectName("muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        self.name_edit = QLineEdit(tr("新しいキャプチャ"), root)
        form.addRow(tr("セッション名"), self.name_edit)

        destination_row = QHBoxLayout()
        self.destination_edit = QLineEdit(str(Path.home() / "Pictures" / "MangaCrisp Captures"), root)
        destination_row.addWidget(self.destination_edit, 1)
        choose_destination = QPushButton(tr("選択..."), root)
        choose_destination.clicked.connect(self.choose_destination)
        destination_row.addWidget(choose_destination)
        resume_session = QPushButton(tr("再開..."), root)
        resume_session.setToolTip(tr("保存済みの未完了キャプチャセッションを開きます。"))
        resume_session.clicked.connect(self.resume_session)
        destination_row.addWidget(resume_session)
        form.addRow(tr("保存先"), destination_row)

        self.display_combo = QComboBox(root)
        form.addRow(tr("ディスプレイ"), self.display_combo)

        permission_row = QHBoxLayout()
        self.permission_label = QLabel(root)
        self.permission_label.setObjectName("muted")
        permission_row.addWidget(self.permission_label, 1)
        self.permission_button = QPushButton(tr("画面収録設定を開く"), root)
        self.permission_button.clicked.connect(self.open_permission_settings)
        permission_row.addWidget(self.permission_button)
        form.addRow(tr("画面収録権限"), permission_row)

        region_row = QHBoxLayout()
        self.region_label = QLabel(tr("未選択"), root)
        self.region_label.setObjectName("muted")
        region_row.addWidget(self.region_label, 1)
        select_region = QPushButton(tr("範囲を選択"), root)
        select_region.clicked.connect(self.select_region)
        region_row.addWidget(select_region)
        full_display = QPushButton(tr("画面全体"), root)
        full_display.clicked.connect(self.select_full_display)
        region_row.addWidget(full_display)
        form.addRow(tr("撮影範囲"), region_row)

        self.hotkey_combo = QComboBox(root)
        for bindings in screen_capture_hotkey_presets():
            self.hotkey_combo.addItem(f"{bindings.capture.label} / Undo: {bindings.undo.label}", bindings)
        form.addRow(tr("撮影ショートカット"), self.hotkey_combo)
        layout.addLayout(form)

        action_row = QHBoxLayout()
        self.start_button = QPushButton(tr("撮影を開始"), root)
        self.start_button.clicked.connect(self.toggle_running)
        action_row.addWidget(self.start_button)
        self.capture_button = QPushButton(tr("今すぐ1枚撮影"), root)
        self.capture_button.clicked.connect(self.capture_with_window_hidden)
        action_row.addWidget(self.capture_button)
        self.undo_button = QPushButton(tr("直前取消"), root)
        self.undo_button.clicked.connect(self.undo_last)
        action_row.addWidget(self.undo_button)
        self.open_button = QPushButton(tr("保存先を開く"), root)
        self.open_button.clicked.connect(self.open_session_directory)
        action_row.addWidget(self.open_button)
        layout.addLayout(action_row)

        self.status_label = QLabel(tr("範囲を選択して撮影を開始してください。"), root)
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.page_list = QListWidget(root)
        self.page_list.setViewMode(QListWidget.IconMode)
        self.page_list.setMovement(QListWidget.Snap)
        self.page_list.setDragDropMode(QListWidget.InternalMove)
        self.page_list.setIconSize(QSize(92, 124))
        self.page_list.setGridSize(QSize(130, 174))
        self.page_list.setSpacing(8)
        self.page_list.model().rowsMoved.connect(self.apply_dragged_order)
        layout.addWidget(self.page_list, 1)

        review_row = QHBoxLayout()
        self.retake_button = QPushButton(tr("選択ページを撮り直す"), root)
        self.retake_button.clicked.connect(self.arm_retake)
        review_row.addWidget(self.retake_button)
        self.rotate_button = QPushButton(tr("右へ90度回転"), root)
        self.rotate_button.clicked.connect(self.rotate_selected)
        review_row.addWidget(self.rotate_button)
        self.delete_button = QPushButton(tr("選択ページを削除"), root)
        self.delete_button.clicked.connect(self.delete_selected)
        review_row.addWidget(self.delete_button)
        review_row.addStretch(1)
        layout.addLayout(review_row)

        output_row = QHBoxLayout()
        self.output_combo = QComboBox(root)
        self.output_combo.addItem("CBZ", "cbz")
        self.output_combo.addItem("ZIP", "zip")
        output_row.addWidget(self.output_combo)
        self.import_check = QCheckBox(tr("完成後に本棚へ追加"), root)
        self.import_check.setChecked(True)
        output_row.addWidget(self.import_check)
        output_row.addStretch(1)
        self.package_button = QPushButton(tr("完成ファイルを作成"), root)
        self.package_button.clicked.connect(self.package_session)
        output_row.addWidget(self.package_button)
        layout.addLayout(output_row)

        self.setCentralWidget(root)
        self.refresh_permission_status()
        self.update_controls()

    def refresh_permission_status(self) -> None:
        state = self.backend.permission_state()
        if state == PermissionState.GRANTED:
            self.permission_label.setText(tr("許可済み（撮影できます）"))
        elif state == PermissionState.DENIED:
            self.permission_label.setText(tr("要設定（初回のみ許可が必要です）"))
        else:
            self.permission_label.setText(tr("この環境では利用できません"))

    def open_permission_settings(self) -> None:
        try:
            self.backend.open_permission_settings()
            self.status_label.setText(
                tr("MangaCrispを有効にした後、アプリを完全に終了して再起動してください。")
            )
        except Exception as exc:  # noqa: BLE001 - Platform settings errors are user-facing.
            self.show_error(tr("画面収録設定を開けません: {error}", error=exc))

    def refresh_displays(self) -> None:
        self.displays = self.backend.list_displays()
        self.display_combo.clear()
        for display in self.displays:
            self.display_combo.addItem(
                f"{display.name} ({display.width} × {display.height})",
                display.identifier,
            )

    def choose_destination(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            tr("キャプチャ保存先を選択"),
            self.destination_edit.text(),
        )
        if selected:
            self.destination_edit.setText(selected)

    def resume_session(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            tr("未完了セッションを選択"),
            self.destination_edit.text(),
        )
        if not selected:
            return
        if self.session is not None:
            self.show_error(tr("現在のセッションを閉じてから再開してください。"))
            return
        try:
            self.session = CaptureSession.open(Path(selected))
            self.coordinator = CaptureCoordinator(self.session)
        except (OSError, ValueError) as exc:
            self.show_error(tr("セッションを再開できません: {error}", error=exc))
            return
        self.name_edit.setText(self.session.manifest.session_name)
        self.destination_edit.setText(str(self.session.directory.parent))
        self.reload_pages()
        self.status_label.setText(
            tr("セッションを再開しました: {count}枚", count=len(self.session.pages))
        )
        self.update_controls()

    def selected_display(self) -> CaptureDisplay | None:
        identifier = self.display_combo.currentData()
        return next((display for display in self.displays if display.identifier == identifier), None)

    def select_region(self) -> None:
        display = self.selected_display()
        if display is None:
            self.show_error(tr("ディスプレイが見つかりません。"))
            return
        self.hide()
        QTimer.singleShot(120, lambda: self._run_region_selector(display))

    def _run_region_selector(self, display: CaptureDisplay) -> None:
        region = RegionSelector.select(display)
        self.show()
        self.raise_()
        self.activateWindow()
        if region is not None:
            self.set_region(region)

    def select_full_display(self) -> None:
        display = self.selected_display()
        if display is None:
            self.show_error(tr("ディスプレイが見つかりません。"))
            return
        self.set_region(
            CaptureRect(
                display_id=display.identifier,
                x=display.x,
                y=display.y,
                width=display.width,
                height=display.height,
            )
        )

    def set_region(self, region: CaptureRect) -> None:
        self.region = region
        self.region_label.setText(
            tr(
                "{width} × {height} px / 位置 {x}, {y}",
                width=region.width,
                height=region.height,
                x=region.x,
                y=region.y,
            )
        )
        self.status_label.setText(tr("撮影範囲を設定しました。"))
        self.update_controls()

    def toggle_running(self) -> None:
        if self.running:
            self.stop_capture()
        else:
            self.start_capture()

    def start_capture(self) -> None:
        if self.region is None:
            self.show_error(tr("先に撮影範囲を選択してください。"))
            return
        if self.hotkey_combo.currentData() is None:
            self.show_error(tr("利用できるグローバルショートカットがありません。"))
            return
        if self.backend.permission_state() != PermissionState.GRANTED:
            state = self.backend.request_permission()
            if state != PermissionState.GRANTED:
                self.refresh_permission_status()
                message = QMessageBox(self)
                message.setWindowTitle(tr("画面収録権限"))
                message.setIcon(QMessageBox.Warning)
                message.setText(tr("画面収録の許可が必要です。"))
                message.setInformativeText(
                    tr(
                        "システム設定でMangaCrispを有効にし、アプリを完全に終了して再起動してください。"
                    )
                )
                open_button = message.addButton(
                    tr("画面収録設定を開く"), QMessageBox.AcceptRole
                )
                message.addButton(QMessageBox.Cancel)
                message.exec()
                if message.clickedButton() is open_button:
                    self.open_permission_settings()
                return
        if self.session is None:
            try:
                destination = Path(self.destination_edit.text()).expanduser()
                self.session = CaptureSession.create(destination, self.name_edit.text())
                self.coordinator = CaptureCoordinator(self.session)
            except Exception as exc:  # noqa: BLE001 - UI boundary must report backend failures.
                self.show_error(tr("セッションを作成できません: {error}", error=exc))
                return
        try:
            bindings = self.hotkey_combo.currentData()
            self.backend.register_hotkeys(
                bindings,
                self.signals.request_capture.emit,
                self.signals.request_undo.emit,
            )
        except Exception as exc:  # noqa: BLE001 - Native hotkey errors vary by macOS version.
            self.show_error(tr("ショートカットを登録できません: {error}", error=exc))
            return
        self.running = True
        self.refresh_permission_status()
        self.start_button.setText(tr("撮影を停止"))
        self.status_label.setText(
            tr(
                "待機中: {capture} で撮影 / {undo} で直前取消。管理画面を最小化します。",
                capture=bindings.capture.label,
                undo=bindings.undo.label,
            )
        )
        self.update_controls()
        if self.isVisible():
            QTimer.singleShot(450, self.showMinimized)

    def stop_capture(self) -> None:
        self.backend.unregister_hotkeys()
        self.running = False
        self.start_button.setText(tr("撮影を開始"))
        self.status_label.setText(tr("撮影を停止しました。保存済みページは維持されています。"))
        self.update_controls()

    def capture_with_window_hidden(self) -> None:
        if self.region is None:
            self.show_error(tr("先に撮影範囲を選択してください。"))
            return
        was_visible = self.isVisible() and not self.isMinimized()
        if was_visible:
            self.hide()
        QTimer.singleShot(180, lambda: self._capture_and_restore(was_visible))

    def _capture_and_restore(self, restore: bool) -> None:
        self.capture_requested()
        if restore:
            QTimer.singleShot(120, self._restore_after_manual_capture)

    def _restore_after_manual_capture(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def capture_requested(self) -> None:
        self.capture_feedback.hide()
        now = time.monotonic()
        if now - self.last_capture_started < CAPTURE_DEBOUNCE_SECONDS:
            return
        self.last_capture_started = now
        if self.region is None:
            return
        if self.session is None:
            destination = Path(self.destination_edit.text()).expanduser()
            try:
                self.session = CaptureSession.create(destination, self.name_edit.text())
                self.coordinator = CaptureCoordinator(self.session)
            except Exception as exc:  # noqa: BLE001 - UI boundary must report storage failures.
                self.show_error(tr("セッションを作成できません: {error}", error=exc))
                return
        if self.coordinator is None:
            return
        try:
            if self.backend.permission_state() != PermissionState.GRANTED:
                self.stop_capture()
                raise PermissionError(
                    tr("画面収録権限が無効になったため撮影を停止しました。")
                )
            self._ensure_disk_space()
            image = self.backend.capture_region(self.region)
            self.coordinator.submit(
                image,
                replace_position=self.retake_position,
                callback=lambda page, error: self.signals.page_saved.emit(page, error),
            )
            self.status_label.setText(
                tr("保存中... 待ち {count}枚", count=self.coordinator.pending)
            )
        except CaptureQueueFullError:
            self.status_label.setText(tr("保存待ちが3枚です。完了後にもう一度撮影してください。"))
        except Exception as exc:  # noqa: BLE001 - Capture backend errors are user-facing.
            self.show_error(tr("撮影できません: {error}", error=exc))

    def on_page_saved(self, page: CapturePage | None, error: BaseException | None) -> None:
        if error is not None or page is None:
            self.show_error(tr("PNGを保存できません: {error}", error=error))
            return
        self.retake_position = None
        self.reload_pages(select_position=page.position)
        warnings = ", ".join(tr(warning.message) for warning in page.warnings)
        if warnings:
            self.status_label.setText(
                tr("{number}枚目を保存しました。警告: {warnings}", number=page.position, warnings=warnings)
            )
        else:
            self.status_label.setText(tr("{number}枚目を保存しました。", number=page.position))
        app = QGuiApplication.instance()
        if app is not None:
            app.setBadgeNumber(len(self.session.pages) if self.session is not None else 0)
        self.capture_feedback.show_message(
            tr(
                "保存 {number}枚",
                number=len(self.session.pages) if self.session is not None else page.position,
            ),
            display=self.selected_display(),
            region=self.region,
        )
        self.update_controls()

    def _ensure_disk_space(self) -> None:
        if self.session is None or self.region is None:
            return
        free = shutil.disk_usage(self.session.directory).free
        required = max(16 * 1024 * 1024, self.region.width * self.region.height * 8)
        if free < required:
            raise OSError(tr("空き容量が少ないため撮影を停止しました。保存先を変更してください。"))

    def undo_last(self) -> None:
        if self.session is None or not self.session.pages:
            self.status_label.setText(tr("取り消せるページはありません。"))
            return
        if self.coordinator is not None and self.coordinator.pending:
            self.status_label.setText(tr("保存完了後に直前取消を実行してください。"))
            return
        page = self.session.undo_last()
        self.retake_position = None
        self.reload_pages()
        self.status_label.setText(tr("{number}枚目を取り消しました。次の撮影で同じ番号を使います。", number=page.position))
        app = QGuiApplication.instance()
        if app is not None:
            app.setBadgeNumber(len(self.session.pages))
        self.capture_feedback.show_message(
            tr("取消 {number}枚目", number=page.position),
            display=self.selected_display(),
            region=self.region,
        )
        self.update_controls()

    def selected_position(self) -> int | None:
        item = self.page_list.currentItem()
        return int(item.data(Qt.UserRole)) if item is not None else None

    def arm_retake(self) -> None:
        position = self.selected_position()
        if position is None:
            self.status_label.setText(tr("撮り直すページを選択してください。"))
            return
        self.retake_position = position
        self.status_label.setText(tr("次の1回で{number}枚目を置き換えます。", number=position))

    def rotate_selected(self) -> None:
        position = self.selected_position()
        if self.session is None or position is None:
            self.status_label.setText(tr("回転するページを選択してください。"))
            return
        try:
            self.session.rotate(position)
            self.reload_pages(select_position=position)
            self.status_label.setText(tr("{number}枚目を右へ90度回転しました。", number=position))
        except Exception as exc:  # noqa: BLE001 - Pillow and filesystem failures are user-facing.
            self.show_error(tr("回転できません: {error}", error=exc))

    def delete_selected(self) -> None:
        position = self.selected_position()
        if self.session is None or position is None:
            self.status_label.setText(tr("削除するページを選択してください。"))
            return
        if QMessageBox.question(
            self,
            tr("ページを削除"),
            tr("{number}枚目をセッションから削除しますか？", number=position),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self.session.delete(position)
        self.reload_pages()
        self.status_label.setText(tr("ページを削除しました。"))
        self.update_controls()

    def apply_dragged_order(self, *_args) -> None:
        if self._reloading_pages or self.session is None:
            return
        positions = [int(self.page_list.item(i).data(Qt.UserRole)) for i in range(self.page_list.count())]
        try:
            self.session.reorder(positions)
            self.reload_pages()
            self.status_label.setText(tr("ページ順を変更しました。"))
        except Exception as exc:  # noqa: BLE001 - Model and filesystem failures are user-facing.
            self.reload_pages()
            self.show_error(tr("ページ順を変更できません: {error}", error=exc))

    def reload_pages(self, *, select_position: int | None = None) -> None:
        self._reloading_pages = True
        try:
            self.page_list.clear()
            if self.session is None:
                return
            for page in self.session.pages:
                warning_codes = {warning.code for warning in page.warnings}
                label = f"{page.position:06d}"
                if warning_codes:
                    label += "\n" + tr("要確認")
                item = QListWidgetItem(QIcon(str(self.session.directory / page.file)), label)
                item.setData(Qt.UserRole, page.position)
                item.setToolTip("\n".join(tr(warning.message) for warning in page.warnings))
                self.page_list.addItem(item)
                if page.position == select_position:
                    self.page_list.setCurrentItem(item)
        finally:
            self._reloading_pages = False

    def package_session(self) -> None:
        if self.session is None or not self.session.pages:
            self.status_label.setText(tr("完成ファイルにするページがありません。"))
            return
        if self.coordinator is not None and self.coordinator.pending:
            self.status_label.setText(tr("PNG保存が完了してから作成してください。"))
            return
        format_name = str(self.output_combo.currentData())
        self.package_button.setEnabled(False)
        self.status_label.setText(tr("完成ファイルを作成中..."))

        def worker() -> None:
            try:
                output = self.session.package(format_name=format_name) if self.session else None
                self.signals.package_done.emit(output, None)
            except Exception as exc:  # noqa: BLE001 - Worker boundary reports errors to the UI.
                self.signals.package_done.emit(None, exc)

        threading.Thread(target=worker, name="capture-package", daemon=True).start()

    def on_package_done(self, output: Path | None, error: BaseException | None) -> None:
        self.package_button.setEnabled(True)
        if error is not None or output is None:
            self.show_error(tr("完成ファイルを作成できません: {error}", error=error))
            return
        self.status_label.setText(tr("完成しました: {path}", path=output))
        if self.import_check.isChecked() and self.on_import is not None:
            self.on_import(output)
            self.status_label.setText(tr("完成して本棚への登録を開始しました: {path}", path=output))

    def open_session_directory(self) -> None:
        path = self.session.directory if self.session is not None else Path(self.destination_edit.text()).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
            open_directory(path)
        except Exception as exc:  # noqa: BLE001 - Platform open errors are user-facing.
            self.show_error(tr("保存先を開けません: {error}", error=exc))

    def update_controls(self) -> None:
        has_pages = self.session is not None and bool(self.session.pages)
        self.capture_button.setEnabled(self.region is not None and not self.running)
        self.undo_button.setEnabled(has_pages)
        self.package_button.setEnabled(has_pages)
        self.retake_button.setEnabled(has_pages)
        self.rotate_button.setEnabled(has_pages)
        self.delete_button.setEnabled(has_pages)
        self.name_edit.setEnabled(self.session is None)
        self.destination_edit.setEnabled(self.session is None)
        self.display_combo.setEnabled(not self.running)
        self.hotkey_combo.setEnabled(not self.running)

    def show_error(self, message: str) -> None:
        self.status_label.setText(message)
        if self.isVisible() and not self.isMinimized():
            QMessageBox.warning(self, tr("連番キャプチャ"), message)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing:
            event.accept()
            return
        self.backend.unregister_hotkeys()
        self.capture_feedback.close()
        app = QGuiApplication.instance()
        if app is not None:
            app.setBadgeNumber(0)
        if self.coordinator is None or self.coordinator.pending == 0:
            if self.coordinator is not None:
                self.coordinator.close(wait=True)
            super().closeEvent(event)
            return
        event.ignore()
        self._closing = True
        self.setEnabled(False)
        self.status_label.setText(tr("保存完了後に閉じます..."))

        def wait_and_close() -> None:
            assert self.coordinator is not None
            self.coordinator.close(wait=True)
            self.signals.close_ready.emit()

        threading.Thread(target=wait_and_close, name="capture-close", daemon=True).start()
