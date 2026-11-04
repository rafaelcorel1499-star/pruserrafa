"""NequiPay Keygen: programa del ADMINISTRADOR para generar el serial de un equipo.

Uso: pega el ID del equipo que te da el cliente, pulsa «Generar serial» y entrégale el serial.
Necesita el archivo private.key junto al programa. Guárdalo en un lugar seguro y no lo compartas.
"""
from __future__ import annotations

import sys
from pathlib import Path

if not getattr(sys, "frozen", False):  # en desarrollo: encontrar src/ (licensing.py)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

import keygen_core as core

STYLE = """
QWidget { background: #F6F1FC; color: #2E1450; font-size: 14px; }
QLabel#title { font-size: 22px; font-weight: 800; color: #8B1FE8; }
QLabel#muted { color: #6F5A8C; }
QLineEdit, QPlainTextEdit { background: white; border: 1px solid #CFC6DD; border-radius: 10px; padding: 8px 10px; }
QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #8B1FE8; }
QPushButton { background: white; border: 1px solid #CFC6DD; border-radius: 10px; padding: 9px 18px; font-weight: 600; }
QPushButton:hover { border-color: #8B1FE8; }
QPushButton#primary { background: #8B1FE8; color: white; border: none; font-weight: 700; }
QPushButton#primary:hover { background: #7415C4; }
"""


class KeygenWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NequiPay Keygen (administrador)")
        self.setMinimumWidth(620)
        self.key = None
        self.key_path = core.base_dir() / "private.key"

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(10)
        t = QLabel("NequiPay Keygen")
        t.setObjectName("title")
        v.addWidget(t)
        self.key_lbl = QLabel()
        self.key_lbl.setObjectName("muted")
        self.key_lbl.setWordWrap(True)
        v.addWidget(self.key_lbl)
        pick = QPushButton("Elegir private.key…")
        pick.clicked.connect(self.choose_key)
        v.addWidget(pick)

        v.addWidget(QLabel("Cliente / nota (opcional, solo para tu historial)"))
        self.client = QLineEdit()
        v.addWidget(self.client)
        v.addWidget(QLabel("ID del equipo (el que muestra la app del cliente)"))
        self.pc_id = QLineEdit()
        self.pc_id.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.pc_id.returnPressed.connect(self.generate)
        v.addWidget(self.pc_id)
        gen = QPushButton("Generar serial")
        gen.setObjectName("primary")
        gen.clicked.connect(self.generate)
        v.addWidget(gen)

        v.addWidget(QLabel("Serial del producto (entrégalo al cliente)"))
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setFont(QFont("Consolas", 11))
        self.out.setFixedHeight(100)
        v.addWidget(self.out)
        row = QHBoxLayout()
        self.copy_btn = QPushButton("Copiar serial")
        self.copy_btn.clicked.connect(self.copy_serial)
        row.addWidget(self.copy_btn)
        row.addStretch()
        v.addLayout(row)
        note = QLabel("Cada serial solo funciona en el equipo cuyo ID se usó. "
                      "Los seriales entregados se anotan en seriales_emitidos.csv.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        v.addWidget(note)
        self.try_load(self.key_path)

    # ------------------------------------------------------------------
    def try_load(self, path: Path):
        try:
            self.key = core.load_private_key(path)
            self.key_path = path
            self.key_lbl.setText(f"Llave cargada: {path}")
        except (OSError, ValueError) as exc:
            self.key = None
            self.key_lbl.setText(f"⚠ No se pudo cargar la llave privada ({path.name}): {exc}\n"
                                 "Copia private.key junto a este programa o elígela con el botón.")

    def choose_key(self):
        f, _ = QFileDialog.getOpenFileName(self, "Seleccionar private.key", str(core.base_dir()),
                                           "Llave (*.key);;Todos (*)")
        if f:
            self.try_load(Path(f))

    def generate(self):
        if self.key is None:
            QMessageBox.warning(self, "Falta la llave", "Primero carga el archivo private.key.")
            return
        try:
            serial = core.generate_serial(self.key, self.pc_id.text())
        except ValueError as exc:
            QMessageBox.warning(self, "ID no válido", str(exc))
            return
        self.out.setPlainText(serial)
        try:
            core.log_issued(core.base_dir(), self.client.text().strip(), self.pc_id.text(), serial)
        except OSError as exc:
            QMessageBox.warning(self, "Historial", f"No se pudo guardar el historial:\n{exc}")

    def copy_serial(self):
        text = self.out.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.copy_btn.setText("¡Copiado!")


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    w = KeygenWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
