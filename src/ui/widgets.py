from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget)

from styles import THEME


@lru_cache(maxsize=1)
def icon_family() -> str:
    fams = set(QFontDatabase.families())
    for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if name in fams:
            return name
    return "Segoe UI Symbol"


def glyph_pixmap(code: int, color: str, size: int = 20) -> QPixmap:
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.TextAntialiasing)
    f = QFont(icon_family())
    f.setPixelSize(size - 2)
    p.setFont(f)
    p.setPen(QColor(color))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, chr(code))
    p.end()
    return pm


def glyph_icon(code: int, color: str, color_on: str | None = None, size: int = 20) -> QIcon:
    ic = QIcon()
    ic.addPixmap(glyph_pixmap(code, color, size), QIcon.Normal, QIcon.Off)
    ic.addPixmap(glyph_pixmap(code, color_on or color, size), QIcon.Normal, QIcon.On)
    return ic


def glyph_label(code: int, size: int = 20, obj: str = "iconAccent") -> QLabel:
    lbl = QLabel(chr(code))
    f = QFont(icon_family())
    f.setPixelSize(size)
    lbl.setFont(f)
    lbl.setObjectName(obj)
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def make_app_icon(color: str = "#8B1FE8", size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(size * 0.03, size * 0.03, size * 0.94, size * 0.94))
    pen = QPen(QColor("white"), size * 0.10, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    k = size / 256
    pts = [QPointF(88 * k, 180 * k), QPointF(88 * k, 76 * k), QPointF(168 * k, 180 * k), QPointF(168 * k, 76 * k)]
    for a, b in zip(pts, pts[1:]):
        p.drawLine(a, b)
    p.end()
    return pm


class SignalBars(QWidget):
    def __init__(self):
        super().__init__()
        self.level = 0
        self.setFixedSize(34, 22)

    def set_level(self, level: int):
        self.level = level
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        on = QColor(THEME.secondary)
        off = QColor(THEME.secondary)
        off.setAlpha(70)
        for i in range(4):
            h = 6 + i * 5
            p.setBrush(on if i < self.level else off)
            p.drawRoundedRect(QRectF(i * 9, 22 - h, 6, h), 2, 2)


class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(54, 30)

    def sizeHint(self):
        return QSize(54, 30)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(THEME.primary) if self.isChecked() else QColor("#C9C2D6"))
        p.drawRoundedRect(self.rect(), 15, 15)
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(27 if self.isChecked() else 3, 3, 24, 24))


class DropZone(QFrame):
    fileSelected = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(96)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.addStretch()
        icon = glyph_label(0xE898, 34)
        text = QLabel("Arrastra tu logo aquí o haz clic para subir\n(PNG, máx 2MB)")
        text.setObjectName("fieldLabel")
        lay.addWidget(icon)
        lay.addSpacing(10)
        lay.addWidget(text)
        lay.addStretch()

    def mousePressEvent(self, _):
        path, _f = QFileDialog.getOpenFileName(self, "Seleccionar logo", "", "Imágenes PNG (*.png)")
        if path:
            self.fileSelected.emit(path)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith(".png") for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            f = u.toLocalFile()
            if f.lower().endswith(".png"):
                self.fileSelected.emit(f)
                break


class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 10, 12)
        lay.setSpacing(14)
        bell = QLabel("🔔")
        bell.setStyleSheet("font-size: 22px;")
        self.label = QLabel()
        close = QPushButton("✕")
        close.setObjectName("toastClose")
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.hide)
        lay.addWidget(bell)
        lay.addWidget(self.label)
        lay.addSpacing(10)
        lay.addWidget(close)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str):
        self.label.setText(text)
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.start(7000)

    def reposition(self):
        p = self.parentWidget()
        if p:
            self.move(p.width() - self.width() - 24, p.height() - self.height() - 24)
