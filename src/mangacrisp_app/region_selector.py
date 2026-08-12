from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QApplication, QDialog

from mangacrisp_app.i18n import tr
from mangacrisp_app.platform.capture_base import CaptureDisplay, CaptureRect


class RegionSelector(QDialog):
    def __init__(self, display: CaptureDisplay, parent=None) -> None:
        super().__init__(parent)
        self.display = display
        self.origin: QPoint | None = None
        self.current: QPoint | None = None
        self.selected_region: CaptureRect | None = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setGeometry(display.x, display.y, display.width, display.height)

    @classmethod
    def select(cls, display: CaptureDisplay, parent=None) -> CaptureRect | None:
        selector = cls(display, parent)
        if selector.exec() == QDialog.Accepted:
            return selector.selected_region
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return
        self.origin = event.position().toPoint()
        self.current = self.origin
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.origin is None:
            return
        self.current = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton or self.origin is None:
            return
        self.current = event.position().toPoint()
        selected = QRect(self.origin, self.current).normalized().intersected(self.rect())
        if selected.width() < 2 or selected.height() < 2:
            self.origin = None
            self.current = None
            self.update()
            return
        self.selected_region = CaptureRect(
            display_id=self.display.identifier,
            x=self.display.x + selected.x(),
            y=self.display.y + selected.y(),
            width=selected.width(),
            height=selected.height(),
        )
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 145))
        selected = QRect()
        if self.origin is not None and self.current is not None:
            selected = QRect(self.origin, self.current).normalized().intersected(self.rect())
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selected, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor("#4da3ff"), 3))
            painter.drawRect(selected)
        painter.setPen(QColor("white"))
        painter.setFont(QApplication.font())
        message = tr("ドラッグして撮影範囲を選択 / Escでキャンセル")
        painter.drawText(self.rect().adjusted(24, 24, -24, -24), Qt.AlignTop | Qt.AlignHCenter, message)
        if not selected.isNull():
            dimensions = f"{selected.width()} × {selected.height()} px"
            painter.drawText(selected.adjusted(8, 8, -8, -8), Qt.AlignTop | Qt.AlignLeft, dimensions)

