from __future__ import annotations

import os
from datetime import datetime

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from sms_parser import format_money
from styles import THEME, build_stylesheet
from ui.payments import PaymentsPanel
from ui.settings import SettingsPage
from ui.widgets import SignalBars, Toast, glyph_icon, glyph_label, make_app_icon

VERSION = "v1.0.0"


def set_prop(w: QWidget, name: str, value):
    w.setProperty(name, value)
    w.style().unpolish(w)
    w.style().polish(w)


class StatCard(QFrame):
    def __init__(self, icon: str | int, title: str):
        super().__init__()
        self.setObjectName("card")
        h = QHBoxLayout(self)
        h.setContentsMargins(18, 16, 18, 16)
        h.setSpacing(16)
        if isinstance(icon, int):
            ic = glyph_label(icon, 24, "iconCircle")
        else:
            ic = QLabel(icon)
            ic.setObjectName("iconCircle")
            ic.setAlignment(Qt.AlignCenter)
        ic.setFixedSize(58, 58)
        v = QVBoxLayout()
        v.setSpacing(0)
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        self.value = QLabel("—")
        self.value.setObjectName("cardValue")
        v.addWidget(self.title)
        v.addWidget(self.value)
        h.addWidget(ic)
        h.addLayout(v, 1)


class DashboardPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(18)
        row = QHBoxLayout()
        row.setSpacing(16)
        self.c_count = StatCard("💳", "Pagos Hoy")
        self.c_total = StatCard("$", "Total Recibido")
        self.c_last = StatCard(0xE823, "Último Pago")
        self.c_state = StatCard(0xE73E, "Estado")
        self.state_pill = QLabel("INACTIVO")
        self.state_pill.setObjectName("statePill")
        set_prop(self.state_pill, "ok", False)
        self.c_state.value.hide()
        self.c_state.layout().itemAt(1).layout().addWidget(self.state_pill, 0, Qt.AlignLeft)
        for c in (self.c_count, self.c_total, self.c_last, self.c_state):
            row.addWidget(c, 1)
        lay.addLayout(row)
        self.panel = PaymentsPanel(db, default_range=1)
        lay.addWidget(self.panel, 1)

    def set_active(self, ok: bool):
        self.state_pill.setText("ACTIVO" if ok else "INACTIVO")
        set_prop(self.state_pill, "ok", ok)

    def refresh(self):
        count, total, last = self.db.stats_today()
        self.c_count.value.setText(str(count))
        self.c_total.value.setText(format_money(total))
        self.c_last.value.setText(format_money(last) if last is not None else "—")
        self.panel.refresh()


class HistoryPage(QWidget):
    def __init__(self, db):
        super().__init__()
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        self.panel = PaymentsPanel(db, default_range=0, with_export=True, title="Historial de Pagos")
        lay.addWidget(self.panel)

    def refresh(self):
        self.panel.refresh()


class MainWindow(QMainWindow):
    def __init__(self, cfg, db, voice):
        super().__init__()
        self.cfg, self.db, self.voice = cfg, db, voice
        self.setWindowTitle("NequiPay Monitor")
        self.setWindowIcon(make_app_icon(cfg["primary"]).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.resize(1200, 780)
        self.setMinimumSize(1100, 680)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())
        body = QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)
        body.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)

        self.dashboard = DashboardPage(db)
        self.history = HistoryPage(db)
        self.settings = SettingsPage(cfg, voice)
        for p in (self.dashboard, self.history, self.settings):
            self.stack.addWidget(p)

        self.toast = Toast(self)
        self._connected = False
        self.apply_theme()
        self.dashboard.refresh()
        self.history.refresh()
        self._tick()
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick)
        self._clock.start(10_000)

    # ------------------------------------------------------------------ construcción
    def _build_header(self) -> QWidget:
        h = QFrame()
        h.setObjectName("header")
        h.setFixedHeight(84)
        lay = QHBoxLayout(h)
        lay.setContentsMargins(22, 0, 22, 0)
        lay.setSpacing(14)
        self.logo = QLabel()
        self.logo.setFixedSize(52, 52)
        self.logo.setAlignment(Qt.AlignCenter)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addStretch()
        self.title = QLabel()
        self.title.setObjectName("appTitle")
        self.biz = QLabel()
        self.biz.setObjectName("bizName")
        titles.addWidget(self.title)
        titles.addWidget(self.biz)
        titles.addStretch()
        lay.addWidget(self.logo)
        lay.addLayout(titles)
        lay.addStretch()
        self.status = QLabel("● USB A7670G Desconectado")
        self.status.setObjectName("status")
        set_prop(self.status, "ok", False)
        sep1, sep2 = QFrame(), QFrame()
        for s in (sep1, sep2):
            s.setObjectName("vsep")
            s.setFixedHeight(40)
        self.cal = glyph_label(0xE787, 22)
        self.clock = QLabel()
        self.clock.setObjectName("clock")
        self.gear = QPushButton()
        self.gear.setObjectName("gear")
        self.gear.setIconSize(QSize(24, 24))
        self.gear.setCursor(Qt.PointingHandCursor)
        self.gear.clicked.connect(lambda: self.go(2))
        for w in (self.status, sep1, self.cal, self.clock, sep2, self.gear):
            lay.addWidget(w, 0, Qt.AlignVCenter)
        return h

    def _build_sidebar(self) -> QWidget:
        sb = QFrame()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(236)
        v = QVBoxLayout(sb)
        v.setContentsMargins(14, 18, 14, 16)
        v.setSpacing(8)
        self.group = QButtonGroup(self)
        self.nav_buttons = []
        for i, (text, code) in enumerate([("Dashboard", 0xE80F), ("Historial", 0xE81C), ("Configuración", 0xE713)]):
            b = QPushButton("  " + text)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setIconSize(QSize(22, 22))
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, idx=i: self.go(idx))
            self.group.addButton(b, i)
            self.nav_buttons.append((b, code))
            v.addWidget(b)
        self.nav_buttons[0][0].setChecked(True)
        v.addStretch()
        line1, line2 = QFrame(), QFrame()
        for l in (line1, line2):
            l.setObjectName("sidebarLine")
        v.addWidget(line1)
        sig = QHBoxLayout()
        sig.setContentsMargins(6, 8, 6, 8)
        txt = QLabel("4G Signal:")
        txt.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.bars = SignalBars()
        sig.addWidget(txt)
        sig.addStretch()
        sig.addWidget(self.bars)
        v.addLayout(sig)
        v.addWidget(line2)
        ver = QLabel(VERSION)
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("font-size: 15px; padding-top: 6px;")
        v.addWidget(ver)
        return sb

    # ------------------------------------------------------------------ navegación / estado
    def go(self, index: int):
        self.stack.setCurrentIndex(index)
        self.nav_buttons[index][0].setChecked(True)
        if index == 0:
            self.dashboard.refresh()
        elif index == 1:
            self.history.refresh()

    def _tick(self):
        n = datetime.now()
        self.clock.setText(n.strftime("%d/%m/%Y  %I:%M ") + ("a.m." if n.hour < 12 else "p.m."))

    def set_connection(self, ok: bool, msg: str):
        self._connected = ok
        self.status.setText("● USB A7670G Conectado" if ok else "● USB A7670G Desconectado")
        self.status.setToolTip(msg)
        set_prop(self.status, "ok", ok)
        self.dashboard.set_active(ok)
        self.settings.set_connection(ok, msg)
        if not ok:
            self.bars.set_level(0)

    def set_signal(self, level: int):
        self.bars.set_level(level)

    def on_payment(self, row: dict, notify: bool = True):
        self.dashboard.refresh()
        self.history.refresh()
        if notify and self.cfg["desktop_notifications"]:
            self.toast.show_message(f"Nuevo pago recibido:\n{format_money(row['amount'])} de {row['sender'].title()}")

    # ------------------------------------------------------------------ tema
    def apply_theme(self):
        P, S = self.cfg["primary"], self.cfg["secondary"]
        THEME.primary, THEME.secondary = P, S
        QApplication.instance().setStyleSheet(build_stylesheet(P, S))
        for b, code in self.nav_buttons:
            b.setIcon(glyph_icon(code, S, P, 22))
        self.gear.setIcon(glyph_icon(0xE713, S, S, 24))
        # logo y nombre
        pm = QPixmap(self.cfg["logo_path"]) if self.cfg["logo_path"] and os.path.exists(self.cfg["logo_path"]) else QPixmap()
        if pm.isNull():
            pm = make_app_icon(P)
        self.logo.setPixmap(pm.scaled(52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.title.setText(f"<span style='color:{P}; font-weight:600'>NequiPay</span> Monitor")
        name = self.cfg["business_name"]
        self.biz.setText(name.upper())
        self.biz.setVisible(bool(name))
        self.setWindowIcon(make_app_icon(P).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        for w in self.findChildren(QWidget):
            w.update()

    # ------------------------------------------------------------------ eventos
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "toast"):
            self.toast.reposition()

    def closeEvent(self, e):
        # Cerrar la ventana solo la oculta: el monitoreo sigue en la bandeja del sistema
        e.ignore()
        self.hide()
