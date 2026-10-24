"""Modal lazy page overview used by the reader's page-list action."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mangacrisp_app.i18n import tr
from mangacrisp_app.page_thumbnails import ThumbnailController

_TILE_WIDTH = 144
_TILE_HEIGHT = 214

PAGE_OVERVIEW_STYLE_SHEET = """
QWidget#pageOverviewCard {
    background: rgba(22, 30, 41, 248);
    border: 1px solid #415163;
    border-radius: 16px;
}
QDialog#pageOverviewBackdrop QLabel {
    background: transparent;
    border: 0;
    color: #eef5f3;
    font-size: 14px;
}
QDialog#pageOverviewBackdrop QLabel#pageOverviewTitle {
    font-size: 22px;
    font-weight: 700;
}
QDialog#pageOverviewBackdrop QLabel#pageOverviewHint {
    color: #aeb8c2;
    font-size: 12px;
}
QDialog#pageOverviewBackdrop QPushButton {
    background: #252c36;
    color: #eef5f3;
    border: 1px solid #414b5c;
    border-radius: 8px;
    min-height: 34px;
    padding: 4px 14px;
    font-size: 14px;
}
QDialog#pageOverviewBackdrop QPushButton:hover,
QDialog#pageOverviewBackdrop QPushButton:focus {
    border: 2px solid #66d9c4;
}
QDialog#pageOverviewBackdrop QPushButton:pressed {
    background: #183d3b;
}
QDialog#pageOverviewBackdrop QPushButton:disabled {
    color: #687482;
    background: #1b222c;
    border-color: #303946;
}
QScrollArea#pageOverviewScroll,
QWidget#pageOverviewViewport,
QWidget#pageOverviewGrid {
    background: transparent;
    border: 0;
}
QScrollArea#pageOverviewScroll QScrollBar:vertical {
    width: 8px;
    margin: 4px 0;
    background: transparent;
}
QScrollArea#pageOverviewScroll QScrollBar::handle:vertical {
    min-height: 30px;
    background: #415163;
    border-radius: 4px;
}
QScrollArea#pageOverviewScroll QScrollBar::handle:vertical:hover {
    background: #66d9c4;
}
QScrollArea#pageOverviewScroll QScrollBar::add-line:vertical,
QScrollArea#pageOverviewScroll QScrollBar::sub-line:vertical {
    height: 0;
}
QToolButton#pageOverviewTile {
    color: #dce8eb;
    background: #182635;
    border: 1px solid #38536a;
    border-radius: 10px;
    padding: 8px;
    font-size: 13px;
}
QToolButton#pageOverviewTile:hover,
QToolButton#pageOverviewTile:focus {
    border: 2px solid #66d9c4;
    background: #1b3440;
}
QToolButton#pageOverviewTile:checked {
    color: #bceee3;
    background: #183d3b;
    border: 2px solid #66d9c4;
}
"""


class _PageTile(QToolButton):
    opened = Signal(int)

    def __init__(self, index: int, parent=None) -> None:
        super().__init__(parent)
        self.index = index

    def mouseDoubleClickEvent(self, event) -> None:
        self.opened.emit(self.index)
        event.accept()


class PageOverviewDialog(QDialog):
    """A modal physical-page selector that decodes only its visible tiles."""

    def __init__(self, parent, pages: Sequence[Path], current_index: int) -> None:
        self.host = parent.window() if parent is not None else None
        super().__init__(self.host, Qt.Dialog | Qt.FramelessWindowHint)
        self.pages = pages
        self.current_index = min(max(0, current_index), max(0, len(pages) - 1))
        self.selected_page_index: int | None = None
        self._generation = 0
        self._shutdown = False
        self._columns = 1
        self._outside_press = None
        self._requested_indexes: set[int] = set()
        self._initial_position_pending = True
        self.setModal(True)
        self.setWindowTitle(tr("ページ一覧"))
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("pageOverviewBackdrop")
        self.setStyleSheet(PAGE_OVERVIEW_STYLE_SHEET)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        self.card = QWidget(self)
        self.card.setObjectName("pageOverviewCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        self.card.setMaximumSize(1000, 800)
        outer.addWidget(self.card, 0, Qt.AlignCenter)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        header = QHBoxLayout()
        title = QLabel(tr("ページ一覧"), self.card)
        title.setObjectName("pageOverviewTitle")
        header.addWidget(title, 1)
        self.close_button = QPushButton("×", self.card)
        self.close_button.setAccessibleName(tr("閉じる"))
        self.close_button.setFixedWidth(44)
        self.close_button.clicked.connect(self.reject)
        header.addWidget(self.close_button)
        card_layout.addLayout(header)
        self.scroll = QScrollArea(self.card)
        self.scroll.setObjectName("pageOverviewScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.grid_widget = QWidget(self.scroll)
        self.grid_widget.setObjectName("pageOverviewGrid")
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setSpacing(10)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.tiles: list[QToolButton] = []
        for index in range(len(pages)):
            tile = _PageTile(index, self.grid_widget)
            tile.setObjectName("pageOverviewTile")
            tile.setCheckable(True)
            tile.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            tile.setText(f"p.{index + 1}\n{tr('読込中')}")
            tile.setAccessibleName(f"p.{index + 1}")
            tile.setFixedSize(_TILE_WIDTH, _TILE_HEIGHT)
            tile.clicked.connect(lambda _checked=False, value=index: self.select_page(value))
            tile.opened.connect(self.open_page)
            self.tiles.append(tile)
        self.scroll.setWidget(self.grid_widget)
        self.scroll.viewport().setObjectName("pageOverviewViewport")
        card_layout.addWidget(self.scroll, 1)
        footer = QHBoxLayout()
        hint = QLabel(tr("ペインの外をクリックして閉じる"), self.card)
        hint.setObjectName("pageOverviewHint")
        footer.addWidget(hint, 1)
        self.go_button = QPushButton(tr("移動"), self.card)
        self.go_button.clicked.connect(self.accept_selection)
        footer.addWidget(self.go_button)
        card_layout.addLayout(footer)
        self.controller = ThumbnailController(pages, self)
        self.controller.thumbnail_ready.connect(self._on_thumbnail_ready)
        self.request_timer = QTimer(self)
        self.request_timer.setSingleShot(True)
        self.request_timer.setInterval(70)
        self.request_timer.timeout.connect(self.request_visible_thumbnails)
        self.initial_position_timer = QTimer(self)
        self.initial_position_timer.setSingleShot(True)
        self.initial_position_timer.timeout.connect(self._position_initial_tile)
        self.scroll.verticalScrollBar().valueChanged.connect(self.schedule_visible_thumbnails)
        self.select_page(self.current_index)
        self.go_button.setEnabled(bool(self.tiles))
        self._set_host_geometry()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._set_host_geometry()
        self._relayout_tiles()
        self.initial_position_timer.start(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_card()
        self._relayout_tiles()
        if not self._initial_position_pending:
            self.schedule_visible_thumbnails()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(4, 12, 23, 185))
        painter.end()

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

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        self.shutdown()
        super().done(result)

    def shutdown(self) -> None:
        """Invalidate requests before the reader releases its own providers."""
        if self._shutdown:
            return
        self._shutdown = True
        self.request_timer.stop()
        self.initial_position_timer.stop()
        self.controller.shutdown()

    def select_page(self, index: int) -> None:
        if index < 0 or index >= len(self.tiles):
            return
        self.selected_page_index = index
        for tile_index, tile in enumerate(self.tiles):
            tile.setChecked(tile_index == index)

    def open_page(self, index: int) -> None:
        self.select_page(index)
        self.accept()

    def accept_selection(self) -> None:
        if self.selected_page_index is not None:
            self.accept()

    def schedule_visible_thumbnails(self) -> None:
        if self._shutdown or self._initial_position_pending:
            return
        self._generation += 1
        self.controller.set_generation(self._generation)
        self._set_requested_indexes(self._visible_thumbnail_indexes())
        self.request_timer.start()

    def request_visible_thumbnails(self) -> None:
        if self._initial_position_pending or not self.isVisible():
            return
        indexes = self._visible_thumbnail_indexes()
        self._set_requested_indexes(indexes)
        self.controller.request(sorted(indexes), self._generation)

    def _visible_thumbnail_indexes(self) -> set[int]:
        viewport = self.scroll.viewport()
        first_row = max(0, self.scroll.verticalScrollBar().value() // (_TILE_HEIGHT + 10) - 1)
        visible_rows = max(1, viewport.height() // (_TILE_HEIGHT + 10) + 1)
        last_row = first_row + visible_rows * 2
        return set(range(first_row * self._columns, min(len(self.tiles), (last_row + 1) * self._columns)))

    def _set_requested_indexes(self, indexes: set[int]) -> None:
        self._requested_indexes = indexes
        for index, tile in enumerate(self.tiles):
            if index in indexes or tile.icon().isNull():
                continue
            tile.setIcon(QIcon())
            tile.setIconSize(QPixmap().size())
            tile.setText(f"p.{index + 1}\n{tr('読込中')}")

    def _position_initial_tile(self) -> None:
        if self._shutdown:
            return
        self._initial_position_pending = False
        if self.tiles:
            self.scroll.ensureWidgetVisible(self.tiles[self.current_index])
            self.tiles[self.current_index].setFocus(Qt.OtherFocusReason)
        self.schedule_visible_thumbnails()

    def _set_host_geometry(self) -> None:
        if self.host is None:
            return
        origin = self.host.mapToGlobal(QPoint(0, 0))
        self.setGeometry(origin.x(), origin.y(), self.host.width(), self.host.height())

    def _fit_card(self) -> None:
        self.card.setFixedSize(
            min(1000, max(1, self.width() - 56)),
            min(800, max(1, self.height() - 56)),
        )

    def _relayout_tiles(self) -> None:
        width = max(1, self.scroll.viewport().width())
        columns = max(1, width // (_TILE_WIDTH + 10))
        if columns == self._columns and self.grid.count() == len(self.tiles):
            return
        while self.grid.count():
            self.grid.takeAt(0)
        self._columns = columns
        for index, tile in enumerate(self.tiles):
            self.grid.addWidget(tile, index // columns, index % columns)

    def _on_thumbnail_ready(self, index: int, image, error: str | None) -> None:
        if index not in self._requested_indexes or index < 0 or index >= len(self.tiles):
            return
        tile = self.tiles[index]
        if error is not None or image.isNull():
            tile.setText(f"p.{index + 1}\n{tr('読込失敗')}")
            return
        tile.setIcon(QIcon(QPixmap.fromImage(image)))
        tile.setIconSize(image.size())
        tile.setText(f"p.{index + 1}")


__all__ = ["PageOverviewDialog"]
