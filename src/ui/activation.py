from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
                               QVBoxLayout)

import licensing
from ui.widgets import glyph_label


class ActivationDialog(QDialog):
    """Se muestra mientras el equipo no tenga un serial válido. Si se cierra, la app no se usa."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NequiPay Monitor - Activación del producto")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(620)
        self.setObjectName("page")
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 24, 28, 22)
        v.setSpacing(12)

        head = QHBoxLayout()
        head.addWidget(glyph_label(0xE72E, 30))
        t = QLabel("Activación del producto")
        t.setObjectName("h1")
        head.addWidget(t)
        head.addStretch()
        v.addLayout(head)

        intro = QLabel("Este equipo todavía no está activado, por lo que la aplicación no puede usarse.\n"
                       "Por favor coloque el serial del producto.")
        intro.setWordWrap(True)
        intro.setObjectName("fieldLabel")
        v.addWidget(intro)

        v.addWidget(self._label("¿No tiene el serial? Entregue al administrador el siguiente ID de su equipo (PC) "
                                "para obtener su clave de producto:", "muted"))
        row = QHBoxLayout()
        self.pc_edit = QLineEdit(licensing.machine_id())
        self.pc_edit.setReadOnly(True)
        self.pc_edit.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: 1px;")
        self.copy_btn = QPushButton(" Copiar ID")
        self.copy_btn.setObjectName("small")
        self.copy_btn.clicked.connect(self._copy_id)
        row.addWidget(self.pc_edit, 1)
        row.addWidget(self.copy_btn)
        v.addLayout(row)

        v.addWidget(self._label("Serial del producto", "fieldLabel"))
        self.serial_edit = QPlainTextEdit()
        self.serial_edit.setPlaceholderText("Pegue aquí el serial que le entregó el administrador")
        self.serial_edit.setFixedHeight(92)
        v.addWidget(self.serial_edit)

        self.error = QLabel()
        self.error.setStyleSheet("color:#B91C1C; font-weight:600;")
        self.error.setWordWrap(True)
        self.error.hide()
        v.addWidget(self.error)

        btns = QHBoxLayout()
        btns.addStretch()
        quit_b = QPushButton("Salir")
        quit_b.setObjectName("ghost")
        self.ok_b = QPushButton("Activar")
        self.ok_b.setObjectName("primary")
        self.ok_b.setDefault(True)
        quit_b.clicked.connect(self.reject)
        self.ok_b.clicked.connect(self._activate)
        btns.addWidget(quit_b)
        btns.addWidget(self.ok_b)
        v.addLayout(btns)

    @staticmethod
    def _label(text: str, obj: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName(obj)
        l.setWordWrap(True)
        return l

    def _copy_id(self):
        QApplication.clipboard().setText(self.pc_edit.text())
        self.copy_btn.setText(" ¡Copiado!")

    def _activate(self):
        serial = self.serial_edit.toPlainText().strip()
        if not serial:
            self._fail("Escriba o pegue el serial del producto.")
        elif not licensing.verify_serial(serial):
            self._fail("El serial no es válido para este equipo. Verifique que lo copió completo y que fue "
                       "generado con el ID de este PC.")
        else:
            try:
                licensing.save_serial(serial)
            except OSError as exc:
                self._fail(f"No se pudo guardar la activación: {exc}")
                return
            self.accept()

    def _fail(self, msg: str):
        self.error.setText(msg)
        self.error.show()
