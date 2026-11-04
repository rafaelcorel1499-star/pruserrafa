from __future__ import annotations

import hashlib
import logging
import os
import sys
import tempfile
from datetime import datetime
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QLockFile, QObject, Signal
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QSystemTrayIcon

import licensing
from app_paths import data_dir
from config import Config
from database import Database
from modem import ModemWorker
from sms_parser import format_money, parse_sms, spoken_phrase
from styles import build_stylesheet
from ui.activation import ActivationDialog
from ui.main_window import MainWindow
from ui.widgets import make_app_icon
from voice import VoiceAnnouncer

log = logging.getLogger("nequipay")


def setup_logging():
    handler = RotatingFileHandler(data_dir() / "nequipay.log", maxBytes=512_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)

    def hook(exc_type, exc, tb):
        log.error("Excepción no controlada", exc_info=(exc_type, exc, tb))
    sys.excepthook = hook


class PaymentProcessor(QObject):
    """Recibe cada SMS (desde el hilo del módem), detecta pagos de Nequi y los guarda."""
    new_payment = Signal(dict)

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def handle_sms(self, sender: str, ts: str, text: str) -> bool:
        payment = parse_sms(text)
        if not payment:
            if "nequi" in text.lower():
                log.info("SMS de Nequi con formato no reconocido: %r", text)
            return False
        key = hashlib.sha1(f"{sender}|{ts}|{text}".encode("utf-8")).hexdigest()
        row = self.db.add_payment(payment, key)
        if row is None:
            return True  # ya estaba guardado (duplicado): se puede borrar de la SIM
        log.info("Pago registrado: %s de %s", payment.amount, payment.sender)
        self.new_payment.emit(row)
        return True


class Controller(QObject):
    def __init__(self, app: QApplication, start_hidden: bool):
        super().__init__()
        self.app = app
        self.cfg = Config()
        self.db = Database(data_dir() / "payments.db")
        self.voice = VoiceAnnouncer(int(self.cfg["volume"]), self.cfg["voice_name"])
        self.processor = PaymentProcessor(self.db)
        self.window = MainWindow(self.cfg, self.db, self.voice)
        self.processor.new_payment.connect(self.on_new_payment)
        self.window.settings.saved.connect(self.on_settings_saved)
        self._port, self.worker = self.cfg["port"], None

        self.tray = QSystemTrayIcon(QIcon(make_app_icon(self.cfg["primary"])), self.window)
        menu = QMenu()
        open_a = QAction("Abrir NequiPay Monitor", menu)
        quit_a = QAction("Salir", menu)
        open_a.triggered.connect(self.show_window)
        quit_a.triggered.connect(self.quit)
        menu.addAction(open_a)
        menu.addSeparator()
        menu.addAction(quit_a)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("NequiPay Monitor")
        self.tray.activated.connect(lambda r: self.show_window() if r in (
            QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        self._menu = menu
        self.tray.show()

        self.start_modem()
        if not start_hidden:
            self.window.show()

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def start_modem(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait(6000)
        self.worker = ModemWorker(self.cfg["port"], int(self.cfg["baudrate"]), self.processor.handle_sms)
        self.worker.status_changed.connect(self.window.set_connection)
        self.worker.signal_changed.connect(self.window.set_signal)
        self.worker.start()

    def on_settings_saved(self):
        self.voice.set_volume(int(self.cfg["volume"]))
        self.voice.set_voice(self.cfg["voice_name"])
        self.tray.setIcon(QIcon(make_app_icon(self.cfg["primary"])))
        if self.cfg["port"] != self._port:
            self._port = self.cfg["port"]
            self.window.set_connection(False, "Reconectando…")
            self.start_modem()

    def on_new_payment(self, row: dict):
        try:
            paid = datetime.fromisoformat(row["paid_at"])
            fresh = abs((datetime.now() - paid).total_seconds()) < 12 * 3600
        except ValueError:
            fresh = True
        self.window.on_payment(row, notify=fresh)
        if not fresh:
            return  # SMS viejo que estaba en la SIM: se guarda pero no se anuncia
        if self.cfg["desktop_notifications"]:
            self.tray.showMessage("Nuevo pago recibido", f"{format_money(row['amount'])} de {row['sender'].title()}",
                                  QSystemTrayIcon.Information, 6000)
        if self.cfg["voice_enabled"]:
            self.voice.speak(spoken_phrase(row["amount"], row["sender"], self.cfg["message_template"]))

    def quit(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait(4000)
        self.voice.stop()
        self.tray.hide()
        self.app.quit()


def main() -> int:
    setup_logging()
    start_hidden = "--minimized" in sys.argv
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setApplicationName("NequiPay Monitor")
    app.setQuitOnLastWindowClosed(False)

    lock = QLockFile(os.path.join(tempfile.gettempdir(), "nequipay-monitor.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(300):
        QMessageBox.information(None, "NequiPay Monitor", "La aplicación ya está en ejecución (revisa la bandeja del sistema).")
        return 0

    # Primer uso en este PC (o serial inválido): no se puede usar hasta activar con un serial del administrador
    if not licensing.is_activated():
        boot_cfg = Config()
        app.setStyleSheet(build_stylesheet(boot_cfg["primary"], boot_cfg["secondary"]))
        if ActivationDialog().exec() != QDialog.Accepted or not licensing.is_activated():
            lock.unlock()
            return 0

    controller = Controller(app, start_hidden)  # noqa: F841  (se mantiene vivo)
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
