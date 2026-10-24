"""Clipped, jointly transformed page surfaces used by the reader.

The viewport owns only page geometry. Source selection, display decoding,
cache keys and reader input handling remain in ``viewer``.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class SpreadViewport(QWidget):
    """A clipped, jointly transformed pair of page panes.

    The labels deliberately remain ordinary ``QLabel`` instances.  Keeping
    their layout in one movable content widget lets the reader add zoom and
    pan without changing its display, correction, or input contracts.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.content = QWidget(self)
        self.page_layout = QHBoxLayout(self.content)
        self.page_layout.setContentsMargins(0, 0, 0, 0)
        self.page_layout.setSpacing(0)

        self.left = QLabel(alignment=Qt.AlignCenter, parent=self.content)
        self.right = QLabel(alignment=Qt.AlignCenter, parent=self.content)
        for label in (self.left, self.right):
            label.setObjectName("pagePane")
            label.setMinimumSize(0, 0)
            label.setMouseTracking(True)
            self.page_layout.addWidget(label, 1)
        self._spread_visible = True
        self._zoom_factor = 1.0
        self._update_fit_minimum_size()

    @property
    def zoom_factor(self) -> float:
        return self._zoom_factor

    def is_fit(self) -> bool:
        return self._zoom_factor == 1.0

    def set_zoom_factor(self, zoom: float, *, anchor: QPoint | None = None, top: bool = False) -> None:
        """Resize the entire spread around ``anchor`` and clamp its pan."""
        zoom = max(0.01, float(zoom))
        old_geometry = self.content.geometry()
        self._zoom_factor = zoom
        width = max(1, round(self.width() * zoom))
        height = max(1, round(self.height() * zoom))
        if anchor is None:
            anchor = QPoint(self.width() // 2, self.height() // 2)
        if old_geometry.width() > 0 and old_geometry.height() > 0:
            relative_x = (anchor.x() - old_geometry.x()) / old_geometry.width()
            relative_y = (anchor.y() - old_geometry.y()) / old_geometry.height()
        else:
            relative_x = relative_y = 0.5
        x = round(anchor.x() - relative_x * width)
        y = 0 if top else round(anchor.y() - relative_y * height)
        self._set_content_geometry(width, height, x, y)

    def pan_by(self, delta_x: int, delta_y: int) -> None:
        """Move the complete spread, never either page independently."""
        geometry = self.content.geometry()
        self._set_content_geometry(
            geometry.width(), geometry.height(), geometry.x() + delta_x, geometry.y() + delta_y
        )

    def reset_view(self) -> None:
        self._zoom_factor = 1.0
        self._set_content_geometry(max(1, self.width()), max(1, self.height()), 0, 0)

    def focus_content_rect(self, rect: tuple[float, float, float, float], *, top: bool = False) -> None:
        """Center a page image rect, or start it at the readable top edge."""
        x, y, width, height = rect
        geometry = self.content.geometry()
        target_x = round(self.width() / 2 - (x + width / 2))
        target_y = round(-y if top else self.height() / 2 - (y + height / 2))
        self._set_content_geometry(
            geometry.width(), geometry.height(), target_x, target_y
        )

    def center_content_point(self, point: tuple[float, float]) -> None:
        """Place a content point at the viewport centre, respecting pan bounds."""
        geometry = self.content.geometry()
        target_x = round(self.width() / 2 - point[0])
        target_y = round(self.height() / 2 - point[1])
        self._set_content_geometry(
            geometry.width(), geometry.height(), target_x, target_y
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        geometry = self.content.geometry()
        width = max(1, round(self.width() * self._zoom_factor))
        height = max(1, round(self.height() * self._zoom_factor))
        self._set_content_geometry(width, height, geometry.x(), geometry.y())

    def _set_content_geometry(self, width: int, height: int, x: int, y: int) -> None:
        if width <= self.width():
            x = (self.width() - width) // 2
        else:
            x = min(0, max(self.width() - width, x))
        if height <= self.height():
            y = (self.height() - height) // 2
        else:
            y = min(0, max(self.height() - height, y))
        self.content.setGeometry(x, y, width, height)
        self.page_layout.invalidate()
        self.page_layout.activate()

    def set_spread_visible(self, visible: bool) -> None:
        """Show both panes for spreads or let the left pane fill single-page mode."""
        self._spread_visible = visible
        self.right.setVisible(visible)
        self._update_fit_minimum_size()
        self.page_layout.invalidate()
        self.page_layout.activate()

    def set_pane_alignments(self, left_alignment, right_alignment) -> None:
        self.left.setAlignment(left_alignment)
        self.right.setAlignment(right_alignment)

    def _update_fit_minimum_size(self) -> None:
        """Keep the old fit-mode space request without constraining zoomed panes."""
        self.setMinimumSize(640 if self._spread_visible else 320, 320)
