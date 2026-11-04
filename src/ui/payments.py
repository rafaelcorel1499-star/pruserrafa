from __future__ import annotations

import csv
from datetime import date, datetime, timedelta

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QDialog, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from sms_parser import format_date, format_money, format_time, parse_amount
from styles import THEME
from ui.widgets import glyph_icon

RANGES = ["Todas las fechas", "Hoy", "Ayer", "Últimos 7 días", "Este mes", "Rango personalizado…"]


class PaymentDetailDialog(QDialog):
    def __init__(self, row: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detalle del pago")
        self.setMinimumWidth(540)
        paid = datetime.fromisoformat(row["paid_at"])
        recv = datetime.fromisoformat(row["received_at"])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)
        title = QLabel("Detalle del pago")
        title.setObjectName("h3")
        lay.addWidget(title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)
        fields = [("Remitente", row["sender"]), ("Valor", format_money(row["amount"])),
                  ("Fecha", format_date(paid)), ("Hora", format_time(paid)),
                  ("Negocio", row["business"] or "—"), ("Canal", row["channel"] or "—"),
                  ("Registrado en el PC", f"{format_date(recv)} {format_time(recv)}")]
        for i, (k, v) in enumerate(fields):
            a, b = QLabel(k), QLabel(v)
            a.setObjectName("muted")
            b.setObjectName("fieldLabel")
            b.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(a, i, 0)
            grid.addWidget(b, i, 1)
        lay.addLayout(grid)
        lbl = QLabel("SMS original")
        lbl.setObjectName("muted")
        lay.addWidget(lbl)
        raw = QPlainTextEdit(row["raw"] or "")
        raw.setReadOnly(True)
        raw.setFixedHeight(90)
        lay.addWidget(raw)
        close = QPushButton("Cerrar")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignRight)


class PaymentsPanel(QFrame):
    def __init__(self, db, default_range: int = 0, with_export: bool = False, title: str = "Pagos Recibidos"):
        super().__init__()
        self.db = db
        self.setObjectName("panel")
        self._rows: list[dict] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(14)

        head = QHBoxLayout()
        bar = QFrame()
        bar.setObjectName("accentBar")
        t = QLabel(title)
        t.setObjectName("h1")
        t.setStyleSheet("font-size: 26px;")
        head.addWidget(bar)
        head.addWidget(t)
        head.addStretch()
        if with_export:
            self.export_btn = QPushButton(" Exportar CSV")
            self.export_btn.setObjectName("small")
            self.export_btn.setIcon(glyph_icon(0xE896, "#5B3A86"))
            self.export_btn.clicked.connect(self.export_csv)
            head.addWidget(self.export_btn)
        lay.addLayout(head)

        # ---- filtros
        f = QHBoxLayout()
        f.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por nombre o valor…")
        self.search.addAction(glyph_icon(0xE721, "#7A6A99"), QLineEdit.LeadingPosition)
        self.date_combo = QComboBox()
        self.date_combo.addItems(RANGES)
        self.date_combo.setCurrentIndex(default_range)
        self.date_combo.setMinimumWidth(170)
        self.d_from, self.d_to = QDateEdit(QDate.currentDate()), QDateEdit(QDate.currentDate())
        for d in (self.d_from, self.d_to):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd/MM/yyyy")
            d.hide()
        self.amin, self.amax = QLineEdit(), QLineEdit()
        self.amin.setPlaceholderText("Valor desde")
        self.amax.setPlaceholderText("Valor hasta")
        self.amin.setFixedWidth(118)
        self.amax.setFixedWidth(118)
        self.btn_filter = QPushButton(" Filtrar")
        self.btn_filter.setObjectName("primary")
        self.btn_filter.setIcon(glyph_icon(0xE71C, "#FFFFFF"))
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setObjectName("link")
        for w in (self.search,):
            f.addWidget(w, 1)
        for w in (self.date_combo, self.d_from, self.d_to, self.amin, self.amax, self.btn_filter, self.btn_clear):
            f.addWidget(w)
        lay.addLayout(f)

        # ---- tabla
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Fecha", "Hora", "Remitente", "Valor", "Estado", "Acción"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 170)
        self.table.setColumnWidth(5, 120)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lay.addWidget(self.table, 1)

        self.empty = QLabel("Aún no hay pagos para mostrar.")
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.empty)
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        lay.addWidget(self.summary)

        # ---- eventos
        self.date_combo.currentIndexChanged.connect(self._on_range)
        self.btn_filter.clicked.connect(self.refresh)
        self.btn_clear.clicked.connect(self.clear_filters)
        self.search.textChanged.connect(self.refresh)
        for w in (self.amin, self.amax):
            w.editingFinished.connect(self.refresh)
        self.d_from.dateChanged.connect(self.refresh)
        self.d_to.dateChanged.connect(self.refresh)
        self._default_range = default_range
        self._on_range()

    # ------------------------------------------------------------------
    def _on_range(self):
        custom = self.date_combo.currentIndex() == 5
        self.d_from.setVisible(custom)
        self.d_to.setVisible(custom)
        self.refresh()

    def clear_filters(self):
        for w in (self.search, self.amin, self.amax):
            w.blockSignals(True)
            w.clear()
            w.blockSignals(False)
        self.date_combo.setCurrentIndex(self._default_range)
        self.refresh()

    def _date_range(self):
        i, today = self.date_combo.currentIndex(), date.today()
        if i == 0:
            return None, None
        if i == 1:
            return today, today
        if i == 2:
            y = today - timedelta(days=1)
            return y, y
        if i == 3:
            return today - timedelta(days=6), today
        if i == 4:
            return today.replace(day=1), today
        return self.d_from.date().toPython(), self.d_to.date().toPython()

    @staticmethod
    def _num(text: str):
        try:
            return parse_amount(text) if text.strip() else None
        except ValueError:
            return None

    def refresh(self):
        d1, d2 = self._date_range()
        self._rows = self.db.query(self.search.text(), d1, d2, self._num(self.amin.text()),
                                   self._num(self.amax.text()), limit=1000)
        self.table.clearContents()
        self.table.setRowCount(0)
        self.table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            dt = datetime.fromisoformat(row["paid_at"])
            vals = [format_date(dt), format_time(dt), row["sender"], format_money(row["amount"])]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 3:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.table.setItem(r, c, it)
            self.table.setCellWidget(r, 4, self._chip())
            self.table.setCellWidget(r, 5, self._view_btn(row))
            self.table.setRowHeight(r, 48)
        self.empty.setVisible(not self._rows)
        total = sum(x["amount"] for x in self._rows)
        n = len(self._rows)
        self.summary.setText(f"{n} pago{'s' if n != 1 else ''}  ·  Total {format_money(total)}")

    def _chip(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(8, 0, 8, 0)
        chip = QLabel("✔  Recibido")
        chip.setObjectName("chip")
        h.addWidget(chip)
        h.addStretch()
        return w

    def _view_btn(self, row: dict) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(8, 0, 8, 0)
        b = QPushButton(" Ver")
        b.setObjectName("small")
        b.setIcon(glyph_icon(0xE7B3, "#5B3A86"))
        b.setIconSize(QSize(18, 18))
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _=False, r=row: PaymentDetailDialog(r, self).exec())
        h.addWidget(b)
        return w

    def export_csv(self):
        if not self._rows:
            QMessageBox.information(self, "Exportar", "No hay pagos para exportar con los filtros actuales.")
            return
        path, _f = QFileDialog.getSaveFileName(self, "Exportar pagos", "pagos_nequi.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Fecha", "Hora", "Remitente", "Valor", "Negocio", "Canal", "SMS"])
            for r in reversed(self._rows):
                dt = datetime.fromisoformat(r["paid_at"])
                w.writerow([format_date(dt), format_time(dt), r["sender"], int(r["amount"]) if float(r["amount"]).is_integer()
                            else r["amount"], r["business"], r["channel"], r["raw"]])
