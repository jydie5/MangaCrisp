"""Fit-only page surfaces used by the reader.

The viewport deliberately owns widget geometry only.  Source selection,
display decoding, cache keys and reader input handling remain in ``viewer`` so
this boundary does not change rendering behavior before zoom and pan exist.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class SpreadViewport(QWidget):
    """Two fit-mode page panes with the reader's established zero-gap layout."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page_layout = QHBoxLayout(self)
        self.page_layout.setContentsMargins(0, 0, 0, 0)
        self.page_layout.setSpacing(0)

        self.left = QLabel(alignment=Qt.AlignCenter, parent=self)
        self.right = QLabel(alignment=Qt.AlignCenter, parent=self)
        for label in (self.left, self.right):
            label.setObjectName("pagePane")
            label.setMinimumSize(320, 320)
            label.setMouseTracking(True)
            self.page_layout.addWidget(label, 1)

    def set_spread_visible(self, visible: bool) -> None:
        """Show both panes for spreads or let the left pane fill single-page mode."""
        self.right.setVisible(visible)
        self.page_layout.invalidate()
        self.page_layout.activate()

    def set_pane_alignments(self, left_alignment, right_alignment) -> None:
        self.left.setAlignment(left_alignment)
        self.right.setAlignment(right_alignment)
