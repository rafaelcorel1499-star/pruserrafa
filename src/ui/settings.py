from __future__ import annotations

import os
import re
import shutil

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QScrollArea, QSizePolicy, QSlider, QVBoxLayout, QWidget)

import autostart
from app_paths import data_dir
from modem import list_serial_ports
import licensing
from sms_parser import DEFAULT_TEMPLATE, format_money, render_message, validate_template
from styles import THEME, mix, norm_hex, valid_hex
from voice import VOICES
from ui.widgets import DropZone, ToggleSwitch, glyph_icon, glyph_label, make_app_icon


class ColorField(QWidget):
    changed = Signal(str)

    def __init__(self, label: str):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        v.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.swatch = QLabel()
        self.swatch.setFixedSize(32, 32)
        self.edit = QLineEdit()
        self.edit.setMaxLength(7)
        self.edit.setPlaceholderText("#8B1FE8")
        self.pick = QPushButton()
        self.pick.setObjectName("small")
        self.pick.setFixedSize(46, 42)
        self.pick.setIcon(glyph_icon(0xE790, "#5B3A86", size=22))
        self.pick.setIconSize(QSize(22, 22))
        self.pick.setToolTip("Elegir color")
        row.addWidget(self.swatch)
        row.addWidget(self.edit, 1)
        row.addWidget(self.pick)
        v.addLayout(row)
        self.edit.textChanged.connect(self._on_text)
        self.pick.clicked.connect(self._pick)

    def set_value(self, hexs: str):
        self.edit.setText(hexs)

    def value(self) -> str:
        return self.edit.text().strip()

    def is_valid(self) -> bool:
        return valid_hex(self.edit.text())

    def _on_text(self, t: str):
        if valid_hex(t):
            c = norm_hex(t)
            self.swatch.setStyleSheet(f"background:{c}; border:1px solid #CFC6DD; border-radius:7px;")
            self.changed.emit(c)
        else:
            self.swatch.setStyleSheet("background:#EEE; border:1px dashed #C00; border-radius:7px;")

    def _pick(self):
        start = QColor(norm_hex(self.value())) if self.is_valid() else QColor("#8B1FE8")
        c = QColorDialog.getColor(start, self, "Elegir color")
        if c.isValid():
            self.edit.setText(c.name().upper())


class MiniPreview(QWidget):
    """Vista previa en miniatura de la app con los colores elegidos."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(300, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(150)
        self.primary, self.secondary = THEME.primary, THEME.secondary

    def set_colors(self, p: str, s: str):
        self.primary, self.secondary = p, s
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        clip = QPainterPath()
        clip.addRoundedRect(r, 14, 14)
        p.setClipPath(clip)
        p.fillRect(r, QColor("#F6F1FC"))
        hh = 34
        p.fillRect(QRectF(r.left(), r.top(), r.width(), hh), QColor("white"))
        p.drawPixmap(int(r.left() + 10), int(r.top() + 6), make_app_icon(self.primary, 64).scaled(
            22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        f = QFont("Segoe UI", 9)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(self.primary))
        p.drawText(QRectF(r.left() + 38, r.top(), 200, hh), Qt.AlignVCenter, "NequiPay Monitor")
        p.setBrush(QColor("#DCFCE7"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(r.right() - 110, r.top() + 8, 70, 18), 9, 9)
        # sidebar
        sb = QRectF(r.left(), r.top() + hh, 44, r.height() - hh)
        g = QLinearGradient(sb.topLeft(), sb.bottomLeft())
        g.setColorAt(0, QColor(self.primary))
        g.setColorAt(1, mix(self.primary, "#000000", 0.38))
        p.fillRect(sb, g)
        p.setBrush(QColor(self.secondary))
        for i in range(3):
            p.drawRoundedRect(QRectF(sb.left() + 12, sb.top() + 14 + i * 24, 20, 14), 4, 4)
        # tarjetas
        card = mix(self.primary, "#FFFFFF", 0.90)
        w = (r.width() - 44 - 50) / 4
        for i in range(4):
            x = sb.right() + 10 + i * (w + 8)
            p.setBrush(card)
            p.drawRoundedRect(QRectF(x, sb.top() + 10, w, 34), 8, 8)
            p.setBrush(QColor(self.primary))
            p.drawEllipse(QRectF(x + 6, sb.top() + 18, 18, 18))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(sb.right() + 10, sb.top() + 54, r.width() - 44 - 20, r.height() - hh - 62), 8, 8)
        p.setBrush(QColor(self.primary))
        p.drawRoundedRect(QRectF(sb.right() + 20, sb.top() + 64, 4, 14), 2, 2)
        p.setBrush(card)
        for i in range(2):
            p.drawRoundedRect(QRectF(sb.right() + 20, sb.top() + 86 + i * 14, r.width() - 44 - 40, 8), 4, 4)


class SettingsPage(QWidget):
    saved = Signal()

    def __init__(self, cfg, voice, parent=None):
        super().__init__(parent)
        self.cfg, self.voice = cfg, voice
        self._pending_logo: str | None = None
        self._logo_cleared = False
        self.setObjectName("page")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("page")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(26, 20, 26, 20)
        lay.setSpacing(16)

        head = QHBoxLayout()
        head.addWidget(glyph_label(0xE713, 30))
        h1 = QLabel("Configuración")
        h1.setObjectName("h1")
        head.addWidget(h1)
        head.addStretch()
        lay.addLayout(head)
        lay.addWidget(self._build_usb())
        lay.addWidget(self._build_identity())
        lay.addWidget(self._build_colors())
        lay.addWidget(self._build_voice())
        lay.addWidget(self._build_message())
        lay.addWidget(self._build_license())
        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        bar = QFrame()
        bar.setObjectName("bottombar")
        hb = QHBoxLayout(bar)
        hb.setContentsMargins(26, 12, 26, 12)
        hb.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("ghost")
        save = QPushButton(" Guardar Cambios")
        save.setObjectName("primary")
        save.setIcon(glyph_icon(0xE74E, "#FFFFFF"))
        cancel.clicked.connect(self.load)
        save.clicked.connect(self.save)
        hb.addWidget(cancel)
        hb.addWidget(save)
        outer.addWidget(bar)
        self.load()

    # ------------------------------------------------------------------ helpers
    def _card(self, title: str, code: int):
        frame = QFrame()
        frame.setObjectName("panel")
        v = QVBoxLayout(frame)
        v.setContentsMargins(22, 16, 22, 18)
        v.setSpacing(12)
        h = QHBoxLayout()
        h.addWidget(glyph_label(code, 24))
        t = QLabel(title)
        t.setObjectName("h3")
        h.addWidget(t)
        h.addStretch()
        v.addLayout(h)
        frame.header = h
        return frame, v

    @staticmethod
    def _field_label(text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("fieldLabel")
        return l

    # ------------------------------------------------------------------ USB
    def _build_usb(self):
        frame, v = self._card("Dispositivo USB", 0xE88E)
        self.conn_pill = QLabel("● Desconectado")
        self.conn_pill.setObjectName("status")
        self.conn_pill.setProperty("ok", False)
        frame.header.addWidget(self.conn_pill)
        row = QHBoxLayout()
        row.setSpacing(24)
        left = QVBoxLayout()
        lr = QHBoxLayout()
        lr.addWidget(self._field_label("Dispositivo de recepción de SMS"))
        lr.addStretch()
        refresh = QPushButton(" Actualizar dispositivos")
        refresh.setObjectName("link")
        refresh.setIcon(glyph_icon(0xE72C, THEME.primary))
        refresh.clicked.connect(lambda: self.reload_ports())
        lr.addWidget(refresh)
        left.addLayout(lr)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(180)
        left.addWidget(self.port_combo)
        mid = QVBoxLayout()
        mid.addWidget(self._field_label("Agregar manualmente (COM Port)"))
        r2 = QHBoxLayout()
        self.manual_edit = QLineEdit()
        self.manual_edit.setPlaceholderText("Ej: COM3")
        add = QPushButton("Agregar")
        add.setObjectName("primary")
        add.clicked.connect(self._add_manual)
        self.manual_edit.returnPressed.connect(self._add_manual)
        r2.addWidget(self.manual_edit, 1)
        r2.addWidget(add)
        mid.addLayout(r2)
        row.addLayout(left, 5)
        row.addLayout(mid, 4)
        v.addLayout(row)
        return frame

    def set_connection(self, ok: bool, msg: str):
        self.conn_pill.setText("● Conectado" if ok else "● Desconectado")
        self.conn_pill.setToolTip(msg)
        self.conn_pill.setProperty("ok", ok)
        self.conn_pill.style().unpolish(self.conn_pill)
        self.conn_pill.style().polish(self.conn_pill)

    def reload_ports(self, select: str | None = None):
        current = select or self.port_combo.currentData() or self.cfg["port"]
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItem("Detección automática (A7670G)", "auto")
        seen = set()
        for p in list_serial_ports():
            self.port_combo.addItem(p.label, p.device)
            seen.add(p.device)
        for m in self.cfg["manual_ports"]:
            if m not in seen:
                self.port_combo.addItem(f"{m} (manual)", m)
                seen.add(m)
        idx = self.port_combo.findData(current)
        if idx < 0 and current not in (None, "auto"):
            self.port_combo.addItem(f"{current} (no detectado)", current)
            idx = self.port_combo.count() - 1
        self.port_combo.setCurrentIndex(max(idx, 0))
        self.port_combo.blockSignals(False)

    def _add_manual(self):
        raw = self.manual_edit.text().strip()
        port = raw.upper() if raw.upper().startswith("COM") else raw
        if not (re.fullmatch(r"COM\d{1,3}", port) or port.startswith("/dev/")):
            QMessageBox.warning(self, "Puerto no válido", "Escribe un puerto válido, por ejemplo: COM3")
            return
        if port not in self.cfg["manual_ports"]:
            self.cfg["manual_ports"].append(port)
            self.cfg.save()
        self.manual_edit.clear()
        self.reload_ports(select=port)

    # ------------------------------------------------------------------ identidad
    def _build_identity(self):
        frame, v = self._card("Identidad del Negocio", 0xE719)
        row = QHBoxLayout()
        row.setSpacing(20)
        left = QVBoxLayout()
        left.addWidget(self._field_label("Logo del negocio (PNG)"))
        self.drop = DropZone()
        self.drop.fileSelected.connect(self._on_logo)
        left.addWidget(self.drop)
        box = QFrame()
        box.setObjectName("logoBox")
        box.setFixedSize(150, 110)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(8, 8, 8, 8)
        self.logo_preview = QLabel("Sin logo")
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_preview.setObjectName("muted")
        bl.addWidget(self.logo_preview)
        clear = QPushButton("Quitar logo")
        clear.setObjectName("link")
        clear.clicked.connect(self._clear_logo)
        mid = QVBoxLayout()
        mid.addWidget(box, 0, Qt.AlignHCenter)
        mid.addWidget(clear, 0, Qt.AlignHCenter)
        right = QVBoxLayout()
        right.addWidget(self._field_label("Nombre del negocio"))
        self.biz_edit = QLineEdit()
        self.biz_edit.setPlaceholderText("Ej: PORTAWARE")
        right.addWidget(self.biz_edit)
        right.addStretch()
        row.addLayout(left, 5)
        row.addLayout(mid)
        row.addLayout(right, 4)
        v.addLayout(row)
        return frame

    def _on_logo(self, path: str):
        if os.path.getsize(path) > 2 * 1024 * 1024:
            QMessageBox.warning(self, "Logo muy pesado", "El logo debe pesar máximo 2 MB.")
            return
        pm = QPixmap(path)
        if pm.isNull():
            QMessageBox.warning(self, "Imagen no válida", "No se pudo leer la imagen PNG.")
            return
        self._pending_logo, self._logo_cleared = path, False
        self._show_logo(pm)

    def _clear_logo(self):
        self._pending_logo, self._logo_cleared = None, True
        self.logo_preview.setPixmap(QPixmap())
        self.logo_preview.setText("Sin logo")

    def _show_logo(self, pm: QPixmap):
        self.logo_preview.setText("")
        self.logo_preview.setPixmap(pm.scaled(132, 92, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    # ------------------------------------------------------------------ colores
    def _build_colors(self):
        frame, v = self._card("Personalización de Colores", 0xE790)
        row = QHBoxLayout()
        row.setSpacing(24)
        self.primary = ColorField("Color Primario")
        self.secondary = ColorField("Color Secundario")
        self.preview = MiniPreview()
        hint = QLabel("El primario se usa en menús, botones y acentos; el secundario en textos e iconos sobre el color primario.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        cols = QVBoxLayout()
        pr = QHBoxLayout()
        pr.setSpacing(24)
        pr.addWidget(self.primary)
        pr.addWidget(self.secondary)
        cols.addLayout(pr)
        cols.addWidget(hint)
        row.addLayout(cols, 5)
        row.addWidget(self.preview, 5)
        v.addLayout(row)
        self.primary.changed.connect(self._update_preview)
        self.secondary.changed.connect(self._update_preview)
        return frame

    def _update_preview(self, *_):
        if self.primary.is_valid() and self.secondary.is_valid():
            self.preview.set_colors(norm_hex(self.primary.value()), norm_hex(self.secondary.value()))

    # ------------------------------------------------------------------ voz
    def _build_voice(self):
        frame, v = self._card("Voz y Notificaciones", 0xE767)
        row = QHBoxLayout()
        row.setSpacing(18)
        self.tg_voice, self.tg_notif = ToggleSwitch(), ToggleSwitch()
        self.chk_auto = QCheckBox("Iniciar con Windows automáticamente")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setMinimumWidth(180)
        self.vol_lbl = QLabel("75%")
        self.vol_lbl.setObjectName("fieldLabel")
        self.vol_lbl.setMinimumWidth(44)
        self.slider.valueChanged.connect(lambda x: self.vol_lbl.setText(f"{x}%"))
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(200)
        for label, name in VOICES:
            self.voice_combo.addItem(label, name)
        test = QPushButton(" Probar voz")
        test.setObjectName("small")
        test.setIcon(glyph_icon(0xE767, "#5B3A86"))
        test.clicked.connect(self._test_voice)
        row.addWidget(self._field_label("Anunciar pagos por voz"))
        row.addWidget(self.tg_voice)
        row.addSpacing(8)
        row.addWidget(self._field_label("Notificaciones de escritorio"))
        row.addWidget(self.tg_notif)
        row.addStretch()
        v.addLayout(row)
        v.addWidget(self.chk_auto)
        r1 = QHBoxLayout()
        r1.setSpacing(12)
        r1.addWidget(self._field_label("Voz"))
        r1.addWidget(self.voice_combo)
        r1.addStretch()
        v.addLayout(r1)
        r2 = QHBoxLayout()
        r2.setSpacing(12)
        r2.addWidget(self._field_label("Volumen de voz"))
        r2.addWidget(self.slider, 1)
        r2.addWidget(self.vol_lbl)
        r2.addWidget(test)
        v.addLayout(r2)
        return frame

    # ------------------------------------------------------------------ mensaje personalizado
    SAMPLE_AMOUNT, SAMPLE_SENDER = 200, "RAFAEL HERNANDO SANCHEZ CAMPO"

    def _build_message(self):
        frame, v = self._card("Mensaje de Voz", 0xE8BD)
        v.addWidget(self._field_label("Texto que se dice al recibir un pago"))
        self.msg_edit = QLineEdit()
        self.msg_edit.setMaxLength(160)
        self.msg_edit.setPlaceholderText(DEFAULT_TEMPLATE)
        v.addWidget(self.msg_edit)
        row = QHBoxLayout()
        row.setSpacing(8)
        b_val = QPushButton(" Insertar {valor}")
        b_nom = QPushButton(" Insertar {nombre}")
        b_def = QPushButton(" Restaurar original")
        for b in (b_val, b_nom, b_def):
            b.setObjectName("small")
        b_val.clicked.connect(lambda: self._insert_token("{valor}"))
        b_nom.clicked.connect(lambda: self._insert_token("{nombre}"))
        b_def.clicked.connect(lambda: self.msg_edit.setText(DEFAULT_TEMPLATE))
        row.addWidget(b_val)
        row.addWidget(b_nom)
        row.addWidget(b_def)
        row.addStretch()
        v.addLayout(row)
        hint = QLabel("Puedes cambiar todo el texto, pero {valor} (monto del pago) y {nombre} (quien envía) "
                      "son obligatorios: los reemplaza la app con los datos reales del SMS.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.msg_preview = QLabel()
        self.msg_preview.setObjectName("fieldLabel")
        self.msg_preview.setWordWrap(True)
        v.addWidget(self.msg_preview)
        self.msg_error = QLabel()
        self.msg_error.setStyleSheet("color:#B91C1C; font-weight:600;")
        self.msg_error.setWordWrap(True)
        v.addWidget(self.msg_error)
        self.msg_edit.textChanged.connect(self._update_message_preview)
        return frame

    def _insert_token(self, token: str):
        self.msg_edit.insert(token)
        self.msg_edit.setFocus()

    def _update_message_preview(self, *_):
        text = self.msg_edit.text()
        err = validate_template(text)
        self.msg_error.setText(err or "")
        self.msg_error.setVisible(bool(err))
        shown = render_message(text, self.SAMPLE_AMOUNT, self.SAMPLE_SENDER)
        self.msg_preview.setText(f"Así sonará: «{shown}»")

    def current_template(self) -> str:
        return " ".join(self.msg_edit.text().split())

    # ------------------------------------------------------------------ licencia
    def _build_license(self):
        frame, v = self._card("Licencia", 0xE72E)
        pill = QLabel("● Activada")
        pill.setObjectName("status")
        pill.setProperty("ok", True)
        frame.header.addWidget(pill)
        v.addWidget(self._field_label("ID de este equipo"))
        row = QHBoxLayout()
        pc = QLineEdit(licensing.machine_id())
        pc.setReadOnly(True)
        copy = QPushButton(" Copiar")
        copy.setObjectName("small")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(pc.text()))
        row.addWidget(pc, 1)
        row.addWidget(copy)
        v.addLayout(row)
        return frame

    def _test_voice(self):
        self.voice.set_volume(self.slider.value())
        self.voice.set_voice(self.voice_combo.currentData())
        self.voice.speak(render_message(self.current_template(), self.SAMPLE_AMOUNT, self.SAMPLE_SENDER))

    # ------------------------------------------------------------------ cargar / guardar
    def load(self):
        c = self.cfg
        self.reload_ports()
        self.biz_edit.setText(c["business_name"])
        self.primary.set_value(c["primary"])
        self.secondary.set_value(c["secondary"])
        self.tg_voice.setChecked(c["voice_enabled"])
        self.tg_notif.setChecked(c["desktop_notifications"])
        self.chk_auto.setChecked(c["autostart"])
        self.slider.setValue(int(c["volume"]))
        self.msg_edit.setText(c["message_template"])
        self._update_message_preview()
        idx = self.voice_combo.findData(c["voice_name"])
        self.voice_combo.setCurrentIndex(max(idx, 0))
        self._pending_logo, self._logo_cleared = None, False
        pm = QPixmap(c["logo_path"]) if c["logo_path"] and os.path.exists(c["logo_path"]) else QPixmap()
        if pm.isNull():
            self._clear_logo()
            self._logo_cleared = False
        else:
            self._show_logo(pm)
        self._update_preview()

    def save(self):
        if not (self.primary.is_valid() and self.secondary.is_valid()):
            QMessageBox.warning(self, "Color no válido",
                                "Los colores deben ser códigos hexadecimales de 6 dígitos, por ejemplo #8B1FE8.")
            return
        err = validate_template(self.current_template())
        if err:
            QMessageBox.warning(self, "Mensaje de voz no válido", err)
            return
        c = self.cfg
        if self._pending_logo:
            dest = data_dir() / "logo.png"
            shutil.copyfile(self._pending_logo, dest)
            c["logo_path"] = str(dest)
        elif self._logo_cleared:
            c["logo_path"] = ""
        c["port"] = self.port_combo.currentData() or "auto"
        c["business_name"] = self.biz_edit.text().strip()
        c["primary"] = norm_hex(self.primary.value())
        c["secondary"] = norm_hex(self.secondary.value())
        c["voice_enabled"] = self.tg_voice.isChecked()
        c["desktop_notifications"] = self.tg_notif.isChecked()
        c["autostart"] = self.chk_auto.isChecked()
        c["volume"] = self.slider.value()
        c["message_template"] = self.current_template()
        c["voice_name"] = self.voice_combo.currentData() or "es-CO-SalomeNeural"
        c.save()
        try:
            autostart.set_autostart(c["autostart"])
        except Exception as exc:
            QMessageBox.warning(self, "Inicio automático", f"No se pudo configurar el inicio con Windows:\n{exc}")
        self.saved.emit()
        QMessageBox.information(self, "Configuración", "Cambios guardados correctamente.")
