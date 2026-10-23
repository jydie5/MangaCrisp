from __future__ import annotations

import re
import shutil
import sys
import threading
from pathlib import Path

from mangacrisp_app.archive_utils import is_image, natural_sort_key
from mangacrisp_app.branding import APP_NAME
from mangacrisp_app.capture_window import CaptureWindow
from mangacrisp_app.correction_cache import remove_enhancement_cache_for_sources
from mangacrisp_app.diagnostics import diagnostics_text
from mangacrisp_app.i18n import (
    current_language,
    load_language_preference,
    save_language_preference,
    tr,
)
from mangacrisp_app.library import (
    Book,
    LibraryPaths,
    LibraryService,
    ReadingState,
    is_library_dir_confirmed,
    managed_book_dir_from_book,
    save_library_settings,
    utc_now_iso,
)
from mangacrisp_app.page_provider import (
    PdfPageIdentityProvider,
    PdfPageList,
    open_pages_for_viewer,
)
from mangacrisp_app.platform import open_directory
from mangacrisp_app.viewer import (
    DEFAULT_FORWARD_PREFETCH_COUNT,
    DEFAULT_PREVIOUS_PREFETCH_COUNT,
    PYSIDE_IMPORT_ERROR,
    SpreadWindow,
    collect_processed_pages,
    default_spread_order,
    show_help_dialog,
)

if PYSIDE_IMPORT_ERROR is None:
    from PySide6.QtCore import (
        QEvent,
        QItemSelectionModel,
        QObject,
        QSize,
        Qt,
        QTimer,
        Signal,
    )
    from PySide6.QtGui import QAction, QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QStackedWidget,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
else:
    QEvent = QItemSelectionModel = QTimer = QObject = QSize = Qt = Signal = QAction = QIcon = QApplication = QFileDialog = QComboBox = QHBoxLayout = QLabel = QListWidget = QListWidgetItem = QMessageBox = QMenu = QPushButton = QStackedWidget = QToolButton = QVBoxLayout = QWidget = None
    QMainWindow = object


class BookshelfSignals(QObject):
    register_progress = Signal(object, object)
    register_done = Signal(object, object)


READING_STATUS_LABELS = {
    "unread": "未読",
    "reading": "読書中",
    "completed": "完了",
}


def volume_badge(title: str) -> str:
    match = re.search(r"第\s*([0-9０-９]+)\s*巻", title)
    if match:
        return f"第{match.group(1)}巻"
    match = re.search(r"\bv(?:ol(?:ume)?\.?)?\s*(\d+[a-zA-Z]?)\b", title, flags=re.IGNORECASE)
    if match:
        return f"v{match.group(1)}"
    return ""


def compact_book_title(title: str, badge: str) -> str:
    compact = title
    if badge:
        compact = compact.replace(badge, "")
        compact = re.sub(r"\bv(?:ol(?:ume)?\.?)?\s*" + re.escape(badge[1:]) + r"\b", "", compact, flags=re.IGNORECASE)
    compact = re.sub(r"[_\s]+", " ", compact).strip(" -_")
    if len(compact) > 19:
        compact = compact[:18] + "…"
    return compact or title[:19]


def bookshelf_label(book: Book, state: ReadingState | None) -> str:
    pages = tr("未解析") if book.page_count is None else tr("{count}ページ", count=book.page_count)
    status_key = READING_STATUS_LABELS.get(book.reading_status)
    status = tr(status_key) if status_key else book.reading_status
    parts = [book.title, pages, status]
    if state is not None:
        parts.append(f"p.{state.page_index + 1}")
    return "    ".join(parts)


def bookshelf_grid_label(book: Book, state: ReadingState | None) -> str:
    badge = volume_badge(book.title)
    title = compact_book_title(book.title, badge)
    page_text = tr("未解析") if book.page_count is None else f"{book.page_count}"
    lines = [badge or title]
    if badge:
        lines.append(title)
    if state is not None:
        lines.append(f"p.{state.page_index + 1} / {page_text}")
    else:
        status_key = READING_STATUS_LABELS.get(book.reading_status)
        lines.append(tr(status_key) if status_key else book.reading_status)
    return "\n".join(lines)


def books_in_folder_display_order(books: list[Book]) -> list[Book]:
    return sorted(
        books,
        key=lambda book: (natural_sort_key(book.title), natural_sort_key(str(Path(book.local_path).parent)), book.id),
    )


def next_book_after_reading(current_book_id: str, books: list[Book]) -> Book | None:
    ordered_books = books_in_folder_display_order(books)
    for index, book in enumerate(ordered_books):
        if book.id == current_book_id:
            if index + 1 >= len(ordered_books):
                return None
            return ordered_books[index + 1]
    return None


def reading_state_from_window(book_id: str, window: SpreadWindow) -> ReadingState:
    return ReadingState(
        book_id=book_id,
        page_index=window.index,
        spread_mode=window.page_layout_mode,
        reading_direction=window.reading_direction,
        cover_single=window.cover_single,
        fit_mode="page",
        correction_preset=window.quality_preset_for_state,
    )


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


def library_location_label(paths: LibraryPaths) -> str:
    return tr(
        "保存先: {path}    使用量: {size}",
        path=paths.library_dir,
        size=format_bytes(directory_size(paths.library_dir)),
    )


def preferred_reader_size(screen_geometry) -> QSize:
    if screen_geometry is None:
        return QSize(1400, 900)
    width = screen_geometry.width()
    height = screen_geometry.height()
    target_width = min(1600, max(1200, int(width * 0.88)))
    target_height = min(1000, max(820, int(height * 0.88)))
    return QSize(min(target_width, width), min(target_height, height))


def bookshelf_shortcuts_text() -> str:
    return "\n".join(
        tr(item)
        for item in [
            "ファイル/フォルダをドロップ: 本棚へ登録",
            "ダブルクリック: 読む",
            "読む: 選択中の本を開く",
            "Command/Ctrl+クリック, Shift+クリック: 複数選択",
            "右クリック: 読む / 本棚から削除",
            "Delete: 選択中の本を本棚から削除。元ZIP/RARは残す",
            "本棚から削除: 確認後、MangaCrisp管理フォルダを削除。元ZIP/RARは残す",
            "保存先を開く: ファイル管理画面でMangaCrisp Libraryを表示",
            "H / ?: このヘルプを表示",
        ]
    )


def dropped_local_paths(mime_data) -> list[Path]:
    if mime_data is None or not mime_data.hasUrls():
        return []
    paths: list[Path] = []
    for url in mime_data.urls():
        if not url.isLocalFile():
            continue
        local_path = url.toLocalFile()
        if local_path:
            paths.append(Path(local_path))
    return paths


DELETE_CONFIRMATION_TITLE_PREVIEW = 3


BOOKSHELF_STYLE_SHEET = """
QWidget#bookshelfRoot {
    background: #0e1622;
    color: #eef5f3;
}
QWidget#bookshelfRoot QLabel#headerTitle {
    color: #f3faf8;
    font-size: 28px;
    font-weight: 700;
}
QWidget#bookshelfRoot QLabel#headerSubtitle {
    color: #aeb8c2;
    font-size: 14px;
}
QWidget#bookshelfRoot QLabel#languageLabel,
QWidget#bookshelfRoot QLabel#libraryLocation,
QWidget#bookshelfRoot QLabel#statusLabel {
    color: #aeb8c2;
}
QWidget#bookshelfRoot QWidget#librarySummaryCard,
QWidget#bookshelfRoot QWidget#libraryInfoCard,
QWidget#bookshelfRoot QWidget#actionBar {
    background: #151f2e;
    border: 1px solid #26364a;
    border-radius: 14px;
}
QWidget#bookshelfRoot QLabel#libraryCount {
    color: #66d9c4;
    font-size: 16px;
    font-weight: 700;
}
QWidget#bookshelfRoot QListWidget#bookGrid {
    background: #0b1320;
    border: 1px solid #26364a;
    border-radius: 14px;
    padding: 10px;
    outline: 0;
}
QWidget#bookshelfRoot QListWidget#bookGrid::item {
    background: #151f2e;
    border: 1px solid #26364a;
    border-radius: 12px;
    color: #eef5f3;
    margin: 6px;
    padding: 10px;
}
QWidget#bookshelfRoot QListWidget#bookGrid::item:hover {
    background: #1c2b3d;
    border-color: #436074;
}
QWidget#bookshelfRoot QListWidget#bookGrid::item:selected {
    background: #183d3b;
    border: 2px solid #66d9c4;
    color: #f3faf8;
}
QWidget#bookshelfRoot QPushButton,
QWidget#bookshelfRoot QToolButton {
    background: #1d293a;
    border: 1px solid #3b4d62;
    border-radius: 9px;
    color: #eef5f3;
    font-size: 14px;
    font-weight: 600;
    min-height: 38px;
    padding: 0 14px;
}
QWidget#bookshelfRoot QPushButton:hover,
QWidget#bookshelfRoot QToolButton:hover {
    border-color: #66d9c4;
}
QWidget#bookshelfRoot QPushButton:pressed,
QWidget#bookshelfRoot QToolButton:pressed {
    background: #183d3b;
    color: #66d9c4;
}
QWidget#bookshelfRoot QPushButton:focus,
QWidget#bookshelfRoot QToolButton:focus {
    border: 2px solid #66d9c4;
}
QWidget#bookshelfRoot QPushButton#primaryButton {
    background: #66d9c4;
    border-color: #66d9c4;
    color: #0b1820;
    font-weight: 700;
    min-width: 112px;
}
QWidget#bookshelfRoot QPushButton#primaryButton:hover {
    background: #8ae8d5;
    border-color: #8ae8d5;
}
QWidget#bookshelfRoot QPushButton#dangerButton {
    background: #242a36;
    border-color: #5a4350;
    color: #ffb8b0;
}
QWidget#bookshelfRoot QPushButton#dangerButton:hover {
    border-color: #ff8d87;
}
QWidget#bookshelfRoot QPushButton:disabled,
QWidget#bookshelfRoot QPushButton#primaryButton:disabled,
QWidget#bookshelfRoot QPushButton#dangerButton:disabled {
    background: #1a2431;
    border-color: #2b394a;
    color: #697888;
}
QWidget#bookshelfRoot QMenu {
    background: #151f2e;
    color: #eef5f3;
    border: 1px solid #3b4d62;
    padding: 6px;
}
QWidget#bookshelfRoot QMenu::item { padding: 6px 14px; }
QWidget#bookshelfRoot QMenu::item:selected { background: #183d3b; color: #66d9c4; }
QWidget#bookshelfRoot QPushButton#iconButton,
QWidget#bookshelfRoot QToolButton#iconButton {
    min-width: 40px;
    max-width: 40px;
    padding: 6px;
}
QWidget#bookshelfRoot QComboBox#languageSelector {
    background: #151f2e;
    border: 1px solid #3b4d62;
    border-radius: 8px;
    color: #eef5f3;
    min-height: 34px;
    min-width: 118px;
    padding: 0 10px;
}
QWidget#bookshelfRoot QComboBox#languageSelector:focus {
    border: 2px solid #66d9c4;
}
QWidget#bookshelfRoot QComboBox#languageSelector QAbstractItemView {
    background: #151f2e;
    border: 1px solid #3b4d62;
    color: #eef5f3;
    selection-background-color: #183d3b;
    selection-color: #66d9c4;
}
QWidget#bookshelfRoot QScrollBar:vertical {
    background: #0e1622;
    width: 10px;
    margin: 0;
}
QWidget#bookshelfRoot QScrollBar::handle:vertical {
    background: #3b4d62;
    border-radius: 5px;
    min-height: 28px;
}
QWidget#bookshelfRoot QScrollBar::add-line:vertical,
QWidget#bookshelfRoot QScrollBar::sub-line:vertical { height: 0; }
QWidget#bookshelfRoot QScrollBar::handle:vertical:hover {
    background: #66d9c4;
}
"""


def context_menu_target_ids(clicked_id: str | None, selected_ids: list[str]) -> list[str]:
    """Books a right-click acts on: the selection when the clicked book is in it, otherwise just that book."""
    if clicked_id is None:
        return []
    if clicked_id in selected_ids:
        return list(selected_ids)
    return [clicked_id]


def delete_confirmation_text(titles: list[str], preview_limit: int = DELETE_CONFIRMATION_TITLE_PREVIEW) -> tuple[str, str]:
    """Question and detail text for one shared delete confirmation, whatever the book count."""
    count = len(titles)
    if count == 1:
        question = tr("この本を本棚から削除しますか？")
    else:
        question = tr("{count}冊を本棚から削除しますか？", count=count)
    shown = titles[:preview_limit]
    lines = list(shown)
    if count > len(shown):
        lines.append(tr("ほか{count}冊", count=count - len(shown)))
    detail = "\n".join(lines) + "\n\n" + tr(
        "MangaCrispが作成した展開済みフォルダ、読書位置、しおりを削除します。\n元のZIP/RAR/7zファイルは削除しません。"
    )
    return question, detail


def delete_outcome_message(deleted_titles: list[str], failed_titles: list[str]) -> str:
    if failed_titles and not deleted_titles:
        if len(failed_titles) == 1:
            return tr("削除できませんでした: {title}", title=failed_titles[0])
        return tr("削除できませんでした: {count}冊 ({titles})", count=len(failed_titles), titles=", ".join(failed_titles))
    if failed_titles:
        return tr(
            "{deleted}冊を削除しました。削除できませんでした: {titles}",
            deleted=len(deleted_titles),
            titles=", ".join(failed_titles),
        )
    if len(deleted_titles) == 1:
        return tr("本棚から削除しました: {title}", title=deleted_titles[0])
    return tr("{count}冊を本棚から削除しました。", count=len(deleted_titles))


class BookshelfWindow(QMainWindow):
    def __init__(self, library: LibraryService | None = None) -> None:
        super().__init__()
        self.library = library or LibraryService.open()
        self.active_reader: SpreadWindow | None = None
        self.active_capture: CaptureWindow | None = None
        self.capture_windows_hidden = False
        self.suppress_reader_return = False
        self.register_queue: list[Path] = []
        self.register_total = 0
        self.register_done_count = 0
        self.register_running = False
        self.signals = BookshelfSignals()
        self.signals.register_progress.connect(self.on_register_progress)
        self.signals.register_done.connect(self.on_register_done)
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._on_application_state_changed)
        self.setWindowTitle(f"{APP_NAME} Bookshelf")
        self.setMinimumSize(900, 620)
        self.resize(1180, 760)
        self.setAcceptDrops(True)

        self.stack = QStackedWidget(self)
        root = QWidget(self.stack)
        root.setObjectName("bookshelfRoot")
        root.setAttribute(Qt.WA_StyledBackground, True)
        root.setStyleSheet(BOOKSHELF_STYLE_SHEET)
        self.bookshelf_page = root
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        header_block = QWidget(root)
        header_block.setObjectName("headerBlock")
        header_block_layout = QVBoxLayout(header_block)
        header_block_layout.setContentsMargins(0, 0, 0, 0)
        header_block_layout.setSpacing(3)
        header = QLabel(APP_NAME, header_block)
        header.setObjectName("headerTitle")
        header_block_layout.addWidget(header)
        header_subtitle = QLabel(
            tr("ローカルのPDF、画像フォルダ、単画像、zip/cbz/rar/cbr/7z/cb7 を本棚へ登録します。"),
            header_block,
        )
        header_subtitle.setObjectName("headerSubtitle")
        header_subtitle.setWordWrap(True)
        header_block_layout.addWidget(header_subtitle)
        header_row.addWidget(header_block, 1)

        summary_card = QWidget(root)
        summary_card.setObjectName("librarySummaryCard")
        summary_card.setMinimumWidth(178)
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(10, 8, 10, 8)
        summary_layout.setSpacing(0)
        self.library_count_label = QLabel("", summary_card)
        self.library_count_label.setObjectName("libraryCount")
        self.library_count_label.setAlignment(Qt.AlignCenter)
        self.library_count_label.setWordWrap(False)
        summary_layout.addWidget(self.library_count_label)
        header_row.addWidget(summary_card)

        help_button = QPushButton("?", root)
        help_button.setObjectName("iconButton")
        help_button.setToolTip(tr("ショートカットを表示"))
        help_button.clicked.connect(self.show_shortcuts_help)
        header_row.addWidget(help_button)
        more_button = QToolButton(root)
        more_button.setObjectName("iconButton")
        more_button.setText("…")
        more_button.setToolTip(tr("その他の操作"))
        more_button.setPopupMode(QToolButton.InstantPopup)
        more_menu = QMenu(more_button)
        copy_diagnostics_action = QAction(tr("診断情報をコピー"), more_menu)
        copy_diagnostics_action.triggered.connect(self.copy_diagnostics)
        more_menu.addAction(copy_diagnostics_action)
        clear_cache_action = QAction(tr("キャッシュを削除"), more_menu)
        clear_cache_action.triggered.connect(self.clear_cache)
        more_menu.addAction(clear_cache_action)
        more_button.setMenu(more_menu)
        header_row.addWidget(more_button)
        language_label = QLabel(tr("言語"), root)
        language_label.setObjectName("languageLabel")
        header_row.addWidget(language_label)
        self.language_combo = QComboBox(root)
        self.language_combo.setObjectName("languageSelector")
        self.language_combo.addItem(tr("システム設定"), "auto")
        self.language_combo.addItem(tr("英語"), "en")
        self.language_combo.addItem(tr("日本語"), "ja")
        preference = load_language_preference(self.library.paths.settings_path)
        preference_index = self.language_combo.findData(preference)
        self.language_combo.setCurrentIndex(max(0, preference_index))
        self.language_combo.currentIndexChanged.connect(self.on_language_preference_changed)
        header_row.addWidget(self.language_combo)
        layout.addLayout(header_row)

        info_card = QWidget(root)
        info_card.setObjectName("libraryInfoCard")
        info_layout = QHBoxLayout(info_card)
        info_layout.setContentsMargins(14, 8, 10, 8)
        info_layout.setSpacing(12)
        self.library_location_label = QLabel("", info_card)
        self.library_location_label.setObjectName("libraryLocation")
        self.library_location_label.setWordWrap(True)
        info_layout.addWidget(self.library_location_label, 1)
        self.open_library_button = QPushButton(tr("保存先を開く"), info_card)
        self.open_library_button.setObjectName("secondaryButton")
        self.open_library_button.clicked.connect(self.open_library_folder)
        info_layout.addWidget(self.open_library_button)
        layout.addWidget(info_card)

        self.list_widget = QListWidget(root)
        self.list_widget.setObjectName("bookGrid")
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setWordWrap(True)
        self.list_widget.setIconSize(QSize(132, 192))
        self.list_widget.setGridSize(QSize(190, 292))
        self.list_widget.setSpacing(16)
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self.show_book_context_menu)
        self.list_widget.itemSelectionChanged.connect(self.update_action_states)
        self.list_widget.setAcceptDrops(True)
        self.list_widget.viewport().setAcceptDrops(True)
        self.list_widget.installEventFilter(self)
        self.list_widget.viewport().installEventFilter(self)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.open_selected_book())
        layout.addWidget(self.list_widget, 1)

        action_bar = QWidget(root)
        action_bar.setObjectName("actionBar")
        buttons = QHBoxLayout(action_bar)
        buttons.setContentsMargins(10, 8, 10, 8)
        buttons.setSpacing(8)
        self.add_file_button = QPushButton(tr("ファイルを追加"), root)
        self.add_file_button.setObjectName("secondaryButton")
        self.add_file_button.clicked.connect(self.add_file)
        buttons.addWidget(self.add_file_button)

        self.add_folder_button = QPushButton(tr("フォルダを追加"), root)
        self.add_folder_button.setObjectName("secondaryButton")
        self.add_folder_button.clicked.connect(self.add_folder)
        buttons.addWidget(self.add_folder_button)

        self.capture_button = QPushButton(tr("画面を連番キャプチャ"), root)
        self.capture_button.setObjectName("secondaryButton")
        self.capture_button.setToolTip(tr("固定範囲をPNGで連番保存し、CBZまたはZIPにまとめます。"))
        self.capture_button.clicked.connect(self.open_capture_window)
        self.capture_button.setVisible(sys.platform in {"darwin", "win32"} or sys.platform.startswith("linux"))
        buttons.addWidget(self.capture_button)

        buttons.addStretch(1)

        self.delete_button = QPushButton(tr("本棚から削除"), root)
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_selected_book)
        buttons.addWidget(self.delete_button)

        self.open_button = QPushButton(tr("読む"), root)
        self.open_button.setObjectName("primaryButton")
        self.open_button.clicked.connect(self.open_selected_book)
        buttons.addWidget(self.open_button)
        layout.addWidget(action_bar)

        self.status_label = QLabel("", root)
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.stack.addWidget(self.bookshelf_page)
        self.setCentralWidget(self.stack)
        self.reload_books()
        QTimer.singleShot(0, self.confirm_library_location_if_needed)

    def reload_books(self) -> None:
        self.list_widget.clear()
        books = books_in_folder_display_order(self.library.books.list_books())
        for book in books:
            state = self.library.reading_states.get(book.id)
            item = QListWidgetItem(bookshelf_grid_label(book, state))
            item.setToolTip(bookshelf_label(book, state))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            item.setSizeHint(QSize(190, 292))
            if book.cover_thumbnail_path and Path(book.cover_thumbnail_path).exists():
                item.setIcon(QIcon(book.cover_thumbnail_path))
            item.setData(Qt.UserRole, book.id)
            self.list_widget.addItem(item)
        self.library_location_label.setText(library_location_label(self.library.paths))
        self.library_count_label.setText(tr("{count}冊 / タイトル昇順", count=len(books)))
        self.status_label.clear()
        self.update_action_states()

    def update_action_states(self) -> None:
        """Keep the primary and destructive actions clear when nothing is selected."""
        has_selection = bool(self.selected_book_ids())
        self.open_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def confirm_library_location_if_needed(self) -> None:
        if is_library_dir_confirmed(self.library.paths):
            return
        message = QMessageBox(self)
        message.setWindowTitle(tr("本棚保存先"))
        message.setIcon(QMessageBox.Information)
        message.setText(tr("MangaCrispの本棚保存先を確認してください。"))
        message.setInformativeText(
            tr(
                "展開済み漫画は容量が大きくなるため、ファイル管理画面で見つけやすい場所に保存します。\n\n現在の保存先:\n{path}",
                path=self.library.paths.library_dir,
            )
        )
        use_button = message.addButton(tr("この場所を使う"), QMessageBox.AcceptRole)
        change_button = message.addButton(tr("変更..."), QMessageBox.ActionRole)
        message.addButton(tr("後で"), QMessageBox.RejectRole)
        message.exec()
        clicked = message.clickedButton()
        if clicked == use_button:
            save_library_settings(self.library.paths, library_dir_confirmed=True)
            self.reload_books()
        elif clicked == change_button:
            self.choose_library_location()

    def on_language_preference_changed(self, _index: int) -> None:
        preference = self.language_combo.currentData()
        save_language_preference(preference, self.library.paths.settings_path)
        QMessageBox.information(
            self,
            tr("言語設定"),
            tr("言語設定を保存しました。MangaCrispを再起動すると反映されます。"),
        )

    def eventFilter(self, watched, event) -> bool:
        if (
            watched in {self.list_widget, self.list_widget.viewport()}
            and event.type() == QEvent.KeyPress
            and event.key() in {Qt.Key_H, Qt.Key_Question}
            and not (event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier))
            and self.stack.currentWidget() is self.bookshelf_page
            and QApplication.activeModalWidget() is None
        ):
            self.show_shortcuts_help()
            return True
        if watched in {self.list_widget, self.list_widget.viewport()} and self.handle_drop_event(event):
            return True
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event) -> None:
        self.accept_drag_event_if_supported(event)

    def dragMoveEvent(self, event) -> None:
        self.accept_drag_event_if_supported(event)

    def dropEvent(self, event) -> None:
        self.accept_drop_event(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key_H, Qt.Key_Question}:
            self.show_shortcuts_help()
            return
        if event.key() in {Qt.Key_Delete, Qt.Key_Backspace} and self.stack.currentWidget() is self.bookshelf_page:
            self.delete_selected_book()
            return
        super().keyPressEvent(event)

    def show_shortcuts_help(self) -> None:
        show_help_dialog(self, bookshelf_shortcuts_text())

    def open_capture_window(self) -> None:
        if self.active_capture is not None:
            self.active_capture.showNormal()
            self.active_capture.raise_()
            self.active_capture.activateWindow()
            return
        try:
            window = CaptureWindow(
                on_import=lambda path: self.enqueue_register_paths([path]),
                on_capture_mode_changed=self.on_capture_mode_changed,
                on_return_to_bookshelf=self.return_from_capture,
            )
        except (OSError, RuntimeError) as exc:
            QMessageBox.warning(
                self,
                tr("連番キャプチャ"),
                tr("この環境では連番キャプチャを開始できません: {error}", error=exc),
            )
            return
        window.setAttribute(Qt.WA_DeleteOnClose)
        window.destroyed.connect(self._capture_window_closed)
        self.active_capture = window
        window.show()

    def _capture_window_closed(self) -> None:
        self.active_capture = None
        self.capture_windows_hidden = False
        if not self.isVisible():
            self.showNormal()

    def on_capture_mode_changed(self, running: bool) -> None:
        self.capture_windows_hidden = running
        if running:
            self.hide()
            if self.active_capture is not None:
                if sys.platform == "win32" or sys.platform.startswith("linux"):
                    # Keep a taskbar entry so the controller can be restored
                    # while global capture remains active. Only macOS can
                    # reopen a hidden window from the Dock.
                    self.active_capture.showMinimized()
                else:
                    self.active_capture.hide()
            return
        self.showNormal()
        if self.active_capture is not None:
            self.active_capture.showNormal()
            self.active_capture.raise_()
            self.active_capture.activateWindow()

    def restore_capture_controller(self) -> None:
        if not self.capture_windows_hidden or self.active_capture is None:
            return
        self.capture_windows_hidden = False
        self.active_capture.showNormal()
        self.active_capture.raise_()
        self.active_capture.activateWindow()

    def _on_application_state_changed(self, state) -> None:
        if state == Qt.ApplicationActive and self.capture_windows_hidden:
            QTimer.singleShot(0, self.restore_capture_controller)

    def return_from_capture(self) -> None:
        self.capture_windows_hidden = False
        if self.active_capture is not None:
            self.active_capture.hide()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def copy_diagnostics(self) -> None:
        text = diagnostics_text(
            book_count=len(self.library.books.list_books()),
            cache_dir=self.library.paths.cache_dir,
        )
        QApplication.clipboard().setText(text)
        self.status_label.setText(tr("診断情報をクリップボードへコピーしました。"))

    def clear_cache(self) -> None:
        message = QMessageBox(self)
        message.setWindowTitle(tr("キャッシュを削除"))
        message.setIcon(QMessageBox.Question)
        message.setText(tr("PDF描画とAI補正のキャッシュを削除しますか？"))
        message.setInformativeText(tr("本棚、元ファイル、読書位置、しおりは削除しません。"))
        message.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        message.setDefaultButton(QMessageBox.No)
        if message.exec() != QMessageBox.Yes:
            return
        shutil.rmtree(self.library.paths.cache_dir, ignore_errors=True)
        self.library.paths.cache_dir.mkdir(parents=True, exist_ok=True)
        self.status_label.setText(tr("キャッシュを削除しました。"))

    def handle_drop_event(self, event) -> bool:
        if event.type() in {QEvent.DragEnter, QEvent.DragMove}:
            self.accept_drag_event_if_supported(event)
            return event.isAccepted()
        if event.type() == QEvent.Drop:
            self.accept_drop_event(event)
            return event.isAccepted()
        return False

    def accept_drag_event_if_supported(self, event) -> None:
        if dropped_local_paths(event.mimeData()):
            event.acceptProposedAction()

    def accept_drop_event(self, event) -> None:
        paths = dropped_local_paths(event.mimeData())
        if not paths:
            return
        event.acceptProposedAction()
        if self.confirm_register_paths(paths, tr("ドロップしたファイル/フォルダ")):
            self.enqueue_register_paths(paths)

    def confirm_register_paths(self, paths: list[Path], source_label: str) -> bool:
        if not paths:
            return False
        archive_suffixes = {".zip", ".cbz", ".rar", ".cbr", ".7z", ".cb7"}
        archive_count = sum(1 for path in paths if path.suffix.lower() in archive_suffixes)
        pdf_count = sum(1 for path in paths if path.suffix.lower() == ".pdf")
        folder_count = sum(1 for path in paths if path.is_dir())
        file_count = len(paths) - folder_count - archive_count - pdf_count
        examples = "\n".join(f"- {path.name}" for path in paths[:5])
        if len(paths) > 5:
            examples += tr("\n- ほか {count} 件", count=len(paths) - 5)
        detail = tr(
            "{source}を本棚へ登録します。\n\n対象: {total}件（圧縮ファイル {archives}件 / PDF {pdfs}件 / フォルダ {folders}件 / ファイル {files}件）\n\n{examples}\n\n圧縮ファイルは展開し、PDFは原本をコピーして表紙だけを生成します。\n元のファイルは削除しません。",
            source=source_label,
            total=len(paths),
            archives=archive_count,
            pdfs=pdf_count,
            folders=folder_count,
            files=file_count,
            examples=examples,
        )
        message = QMessageBox(self)
        message.setWindowTitle(tr("本棚へ登録"))
        message.setIcon(QMessageBox.Question)
        message.setText(tr("展開して本棚へ登録しますか？"))
        message.setInformativeText(detail)
        message.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        message.setDefaultButton(QMessageBox.Yes)
        if message.exec() != QMessageBox.Yes:
            self.status_label.setText(tr("登録をキャンセルしました。"))
            return False
        self.status_label.setText(detail.splitlines()[0])
        return True

    def choose_library_location(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("本棚保存先を選択"), str(self.library.paths.library_dir))
        if not path:
            return
        new_library_dir = Path(path).expanduser()
        try:
            self.move_library_storage(new_library_dir)
        except Exception as exc:
            self.status_label.setText(tr("保存先を変更できません: {error}", error=exc))
            return
        save_library_settings(self.library.paths, library_dir_confirmed=True)
        self.reload_books()
        self.status_label.setText(tr("保存先を変更しました: {path}", path=self.library.paths.library_dir))

    def move_library_storage(self, new_library_dir: Path) -> None:
        old_paths = self.library.paths
        old_library_dir = old_paths.library_dir.expanduser()
        new_paths = old_paths.with_library_dir(new_library_dir)
        if old_library_dir == new_paths.library_dir:
            self.library.paths.ensure()
            return
        new_paths.library_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(old_library_dir.iterdir(), key=lambda item: item.name) if old_library_dir.exists() else []:
            destination = new_paths.library_dir / source.name
            if destination.exists():
                continue
            source.replace(destination)
        for book in self.library.books.list_books():
            local_path = rewrite_visible_library_path(book.local_path, old_library_dir, new_paths.library_dir)
            cover_path = (
                rewrite_visible_library_path(book.cover_thumbnail_path, old_library_dir, new_paths.library_dir)
                if book.cover_thumbnail_path
                else book.cover_thumbnail_path
            )
            if local_path != book.local_path or cover_path != book.cover_thumbnail_path:
                self.library.books.upsert(book.with_updates(local_path=local_path, cover_thumbnail_path=cover_path))
        try:
            old_library_dir.rmdir()
        except OSError:
            pass
        self.library.paths = new_paths
        self.library.importer.paths = new_paths

    def add_file(self) -> None:
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            tr("本棚に追加"),
            str(Path.home()),
            "PDF, images and archives (*.pdf *.zip *.cbz *.rar *.cbr *.7z *.cb7 *.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff *.avif);;All files (*)",
        )
        self.enqueue_register_paths([Path(path) for path in paths])

    def add_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("画像フォルダを本棚に追加"), str(Path.home()))
        if path:
            self.enqueue_register_paths([Path(path)])

    def enqueue_register_paths(self, paths: list[Path]) -> None:
        if not paths:
            return
        self.register_queue.extend(paths)
        self.register_total += len(paths)
        self.status_label.setText(tr("取り込み待ち {count}件", count=len(self.register_queue)))
        self.start_next_register()

    def register_path(self, path: Path) -> None:
        self.enqueue_register_paths([path])

    def start_next_register(self) -> None:
        if self.register_running:
            return
        if not self.register_queue:
            self.register_total = 0
            self.register_done_count = 0
            return
        path = self.register_queue.pop(0)
        self.register_running = True
        position = self.register_done_count + 1
        total = self.register_done_count + 1 + len(self.register_queue)
        self.status_label.setText(
            tr("取り込み中 {position}/{total}: {name}", position=position, total=total, name=path.name)
        )
        threading.Thread(target=self._register_worker, args=(path,), daemon=True).start()

    def _register_worker(self, path: Path) -> None:
        worker_library = LibraryService.open(self.library.paths)
        try:
            books = worker_library.scanner.scan_many(path)
            self.signals.register_progress.emit(
                books,
                tr("内容を確認しました。取り込み中: {name}", name=path.name),
            )
            imported_books = worker_library.import_local_books(path)
            self.signals.register_done.emit(imported_books, None)
        except Exception as exc:
            self.signals.register_done.emit(None, exc)
        finally:
            worker_library.close()

    def on_register_progress(self, books: list[Book] | None, message: str | None) -> None:
        self.reload_books()
        if message:
            self.status_label.setText(message)

    def on_register_done(self, books: list[Book] | None, error: Exception | None) -> None:
        self.register_running = False
        self.register_done_count += 1
        if error is not None:
            self.status_label.setText(tr("登録失敗: {error}", error=error))
            self.start_next_register()
            return
        self.reload_books()
        label = ("、" if current_language() == "ja" else ", ").join(
            book.title for book in (books or [])[:2]
        )
        if books and len(books) > 2:
            label += tr(" ほか{count}冊", count=len(books) - 2)
        if self.register_queue:
            self.status_label.setText(tr("登録しました: {label}", label=label))
            self.start_next_register()
        else:
            self.status_label.setText(tr("登録しました: {label}", label=label))
            self.register_total = 0
            self.register_done_count = 0

    def set_register_buttons_enabled(self, enabled: bool) -> None:
        self.add_file_button.setEnabled(enabled)
        self.add_folder_button.setEnabled(enabled)

    def open_library_folder(self) -> None:
        self.library.paths.library_dir.mkdir(parents=True, exist_ok=True)
        try:
            open_directory(self.library.paths.library_dir)
        except Exception as exc:
            self.status_label.setText(tr("保存先を開けません: {error}", error=exc))

    def selected_book(self) -> Book | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        book_id = item.data(Qt.UserRole)
        return self.library.books.get(book_id)

    def selected_book_ids(self) -> list[str]:
        ids: list[str] = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item is not None and item.isSelected():
                ids.append(item.data(Qt.UserRole))
        return ids

    def show_book_context_menu(self, position) -> None:
        menu = self.build_book_context_menu(self.list_widget.itemAt(position))
        if menu is not None:
            menu.exec(self.list_widget.viewport().mapToGlobal(position))

    def build_book_context_menu(self, item) -> QMenu | None:
        """Select the clicked book unless it is already part of the selection, then build its menu."""
        if item is None:
            return None
        clicked_id = item.data(Qt.UserRole)
        target_ids = context_menu_target_ids(clicked_id, self.selected_book_ids())
        if clicked_id not in self.selected_book_ids():
            self.list_widget.clearSelection()
            item.setSelected(True)
        self.list_widget.setCurrentItem(item, QItemSelectionModel.NoUpdate)
        menu = QMenu(self.list_widget)
        read_action = QAction(tr("読む"), menu)
        read_action.triggered.connect(lambda: self.open_book(clicked_id))
        menu.addAction(read_action)
        delete_label = tr("本棚から削除") if len(target_ids) == 1 else tr("{count}冊を本棚から削除", count=len(target_ids))
        delete_action = QAction(delete_label, menu)
        delete_action.triggered.connect(lambda: self.delete_books(target_ids))
        menu.addAction(delete_action)
        return menu

    def delete_selected_book(self) -> None:
        self.delete_books(self.selected_book_ids())

    def delete_books(self, book_ids: list[str]) -> None:
        books = [book for book in (self.library.books.get(book_id) for book_id in book_ids) if book is not None]
        if not books:
            self.status_label.setText(tr("削除する本を選んでください。"))
            return
        question, detail = delete_confirmation_text([book.title for book in books])
        message = QMessageBox(self)
        message.setWindowTitle(tr("本棚から削除"))
        message.setIcon(QMessageBox.Warning)
        message.setText(question)
        message.setInformativeText(detail)
        message.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        message.setDefaultButton(QMessageBox.No)
        if message.exec() != QMessageBox.Yes:
            self.status_label.setText(tr("削除をキャンセルしました。"))
            return
        deleted: list[str] = []
        failed: list[str] = []
        for book in books:
            try:
                self.remove_enhancement_cache(book)
                removed = self.library.delete_book(book.id)
            except OSError:
                removed = False
            (deleted if removed else failed).append(book.title)
        self.reload_books()
        self.status_label.setText(delete_outcome_message(deleted, failed))

    def remove_enhancement_cache(self, book: Book) -> None:
        book_dir = managed_book_dir_from_book(book, self.library.paths.library_dir)
        if book_dir is None or not book_dir.is_dir():
            return

        if book.file_kind == "pdf":
            pdf_path = Path(book.local_path).expanduser()
            if not pdf_path.is_file():
                return
            if book.page_count is not None:
                try:
                    # A recorded page count is enough to enumerate keys.  Do
                    # not open or render a PDF during cache cleanup.
                    pages = PdfPageIdentityProvider(pdf_path, book.page_count)
                except OSError:
                    return
            else:
                try:
                    # Legacy records without a count still use the lazy PDF
                    # provider; construction counts pages but materializes none.
                    pages = PdfPageList(pdf_path, self.library.paths.cache_dir / "pdf-render")
                except (OSError, RuntimeError):
                    return
            remove_enhancement_cache_for_sources(pages)
            return

        sources = [path for path in book_dir.rglob("*") if path.is_file() and is_image(path)]
        remove_enhancement_cache_for_sources(sources)

    def open_selected_book(self) -> None:
        book = self.selected_book()
        if book is None:
            self.status_label.setText(tr("読む本を選んでください。"))
            return
        self.open_book(book.id)

    def open_book(self, book_id: str, fullscreen: bool = False) -> None:
        book = self.library.books.get(book_id)
        if book is None:
            self.status_label.setText(tr("本が見つかりません。"))
            return
        source = Path(book.local_path)
        try:
            pages, cleanup_dir = open_pages_for_viewer(source)
        except Exception as exc:
            self.status_label.setText(tr("読み込み失敗: {error}", error=exc))
            return
        if not pages:
            self.status_label.setText(tr("画像が見つかりません: {source}", source=source))
            return
        state = self.library.reading_states.get(book.id)
        next_book = next_book_after_reading(book.id, self.library.books.list_books())
        reading_direction = state.reading_direction if state and state.reading_direction in {"rtl", "ltr"} else "rtl"
        cover_single = state.cover_single if state else True
        initial_page_layout = state.spread_mode if state and state.spread_mode in {"spread", "single"} else "spread"
        initial_page_index = state.page_index if state else 0
        initial_quality_preset = state.correction_preset if state else None
        self.close_active_reader(return_to_bookshelf=False)
        window = SpreadWindow(
            pages,
            book.title,
            cleanup_dir,
            processed_pages=collect_processed_pages(pages, None),
            reading_direction=reading_direction,
            spread_order=default_spread_order(reading_direction),
            cover_single=cover_single,
            auto_prefetch=True,
            prefetch_count=DEFAULT_FORWARD_PREFETCH_COUNT,
            previous_prefetch_count=DEFAULT_PREVIOUS_PREFETCH_COUNT,
            page_changed_callback=lambda _index: self.save_reading_state(book.id, window),
            bookmark_callback=lambda page_index: self.add_bookmark(book.id, page_index),
            bookmarks_provider=lambda: self.library.bookmarks.list_for_book(book.id),
            bookmark_delete_callback=lambda bookmark_id: self.delete_bookmark(book.id, bookmark_id),
            next_book_callback=(lambda: self.open_next_book_from_window(book.id, window)) if next_book else None,
            next_book_label=next_book.title if next_book else None,
            close_callback=self.on_reader_closed,
            settings_path=self.library.paths.settings_path,
            embedded=True,
            parent=self.stack,
            initial_page_index=initial_page_index,
            initial_page_layout=initial_page_layout,
            initial_quality_preset=initial_quality_preset,
        )
        self.active_reader = window
        self.stack.addWidget(window)
        self.stack.setCurrentWidget(window)
        self.setWindowTitle(f"{APP_NAME} - {book.title}")
        if fullscreen:
            window.toggle_fullscreen()
        elif not self.isMaximized():
            screen = self.screen()
            geometry = screen.availableGeometry() if screen is not None else None
            self.resize(preferred_reader_size(geometry))
        window.setFocus(Qt.ActiveWindowFocusReason)

    def open_next_book_from_window(self, current_book_id: str, window: SpreadWindow) -> None:
        next_book = next_book_after_reading(current_book_id, self.library.books.list_books())
        if next_book is None:
            window.statusBar().showMessage(tr("次の巻はありません。"))
            return
        self.save_reading_state(current_book_id, window)
        was_fullscreen = window.is_fullscreen
        self.suppress_reader_return = True
        window.close()
        self.suppress_reader_return = False
        self.open_book(next_book.id, fullscreen=was_fullscreen)

    def close_active_reader(self, return_to_bookshelf: bool = True) -> None:
        if self.active_reader is None:
            return
        self.suppress_reader_return = not return_to_bookshelf
        self.active_reader.close()
        self.suppress_reader_return = False

    def on_reader_closed(self, window: SpreadWindow) -> None:
        if self.active_reader is window:
            self.active_reader = None
        if self.stack.indexOf(window) >= 0:
            self.stack.removeWidget(window)
        window.deleteLater()
        self.reload_books()
        if not self.suppress_reader_return:
            self.stack.setCurrentWidget(self.bookshelf_page)
            self.setWindowTitle(f"{APP_NAME} Bookshelf")
            self.raise_()
            self.activateWindow()

    def save_reading_state(self, book_id: str, window: SpreadWindow) -> None:
        self.library.reading_states.save(reading_state_from_window(book_id, window))
        book = self.library.books.get(book_id)
        if book is not None:
            self.library.books.upsert(book.with_updates(reading_status="reading", last_opened_at=utc_now_iso()))

    def add_bookmark(self, book_id: str, page_index: int) -> bool:
        if self.library.books.get(book_id) is None:
            return False
        if any(bookmark.page_index == page_index for bookmark in self.library.bookmarks.list_for_book(book_id)):
            return False
        self.library.bookmarks.add(book_id, page_index, label=f"p.{page_index + 1}")
        return True

    def delete_bookmark(self, book_id: str, bookmark_id: str) -> bool:
        if not any(bookmark.id == bookmark_id for bookmark in self.library.bookmarks.list_for_book(book_id)):
            return False
        return self.library.bookmarks.delete(bookmark_id)

    def closeEvent(self, event) -> None:
        if self.active_reader is not None:
            self.close_active_reader(return_to_bookshelf=False)
        self.library.close()
        super().closeEvent(event)


def rewrite_visible_library_path(path_text: str, old_root: Path, new_root: Path) -> str:
    old = str(old_root.expanduser())
    new = str(new_root.expanduser())
    if path_text == old:
        return new
    prefix = old + "/"
    if path_text.startswith(prefix):
        return new + "/" + path_text[len(prefix):]
    return path_text
