"""Comunicación con el módem USB A7670G (SIMCom) mediante comandos AT.

Lee los SMS de la SIM en modo texto, los entrega a `handler(sender, timestamp, text)`
y borra de la SIM únicamente los que el handler reconoció como pagos de Nequi.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

import serial
from serial.tools import list_ports
from PySide6.QtCore import QThread, Signal

log = logging.getLogger("nequipay")

_END = re.compile(rb"\r\n(OK|ERROR|\+CM[ES] ERROR:[^\r\n]*)\r\n")
_HDR = re.compile(r'^\+CMGL:\s*(\d+),"([^"]*)","([^"]*)"(?:,(?:"[^"]*")?)?(?:,"([^"]*)")?')


@dataclass
class PortInfo:
    device: str
    description: str
    likely: bool
    is_at: bool

    @property
    def label(self) -> str:
        base = self.description.replace(f"({self.device})", "").strip() or "Puerto serie"
        return f"{'A7670G - ' if self.likely else ''}{base} ({self.device})"


@dataclass
class Sms:
    index: int
    sender: str
    ts: str
    text: str


def list_serial_ports() -> list[PortInfo]:
    out = []
    for p in list_ports.comports():
        desc = " ".join(filter(None, [p.description, p.manufacturer, p.product])).lower()
        likely = p.vid == 0x1E0E or any(k in desc for k in ("a7670", "simcom", "simtech"))
        is_at = likely and "at" in re.findall(r"[a-z]+", desc)
        out.append(PortInfo(p.device, p.description or "Puerto serie", likely, is_at))
    out.sort(key=lambda x: (not x.is_at, not x.likely, x.device))
    return out


def probe_port(device: str, baud: int = 115200) -> bool:
    try:
        with serial.Serial(device, baud, timeout=0.3, write_timeout=1) as s:
            for _ in range(2):
                s.reset_input_buffer()
                s.write(b"AT\r")
                time.sleep(0.4)
                if b"OK" in s.read(64):
                    return True
    except Exception:
        pass
    return False


def decode_text(t: str) -> str:
    """Algunos módems entregan SMS con acentos en UCS2 hexadecimal."""
    s = t.strip()
    if len(s) >= 8 and len(s) % 4 == 0 and re.fullmatch(r"[0-9A-Fa-f]+", s):
        try:
            return bytes.fromhex(s).decode("utf-16-be")
        except Exception:
            pass
    return t


def parse_cmgl(raw: str) -> list[Sms]:
    msgs, cur = [], None
    for line in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        m = _HDR.match(line)
        if m:
            if cur:
                msgs.append(cur)
            cur = {"index": int(m[1]), "sender": decode_text(m[3]), "ts": m[4] or "", "lines": []}
        elif cur is not None:
            if line.strip() in ("OK", "ERROR"):
                msgs.append(cur)
                cur = None
            else:
                cur["lines"].append(line)
    if cur:
        msgs.append(cur)
    return [Sms(c["index"], c["sender"], c["ts"], decode_text("\n".join(c["lines"]).strip())) for c in msgs]


def csq_to_bars(rssi: int) -> int:
    if rssi in (0, 99) or rssi > 31:
        return 0
    return 1 if rssi < 10 else 2 if rssi < 15 else 3 if rssi < 20 else 4


class ModemWorker(QThread):
    status_changed = Signal(bool, str)
    signal_changed = Signal(int)

    def __init__(self, port: str, baud: int, handler: Callable[[str, str, str], bool], parent=None):
        super().__init__(parent)
        self.port, self.baud, self.handler = port, baud, handler
        self._stop_evt = threading.Event()

    def stop(self):
        self._stop_evt.set()

    # ------------------------------------------------------------------ main loop
    def run(self):
        while not self._stop_evt.is_set():
            ser = None
            try:
                device = self._resolve_port()
                if not device:
                    self.status_changed.emit(False, "Módem A7670G no encontrado")
                    self.signal_changed.emit(0)
                else:
                    ser = serial.Serial(device, self.baud, timeout=0.3, write_timeout=3)
                    self._init_modem(ser)
                    log.info("Módem conectado en %s", device)
                    self.status_changed.emit(True, f"Conectado en {device}")
                    self._loop(ser)
            except Exception as exc:
                log.warning("Módem: %s", exc)
                self.status_changed.emit(False, str(exc))
                self.signal_changed.emit(0)
            finally:
                if ser:
                    try:
                        ser.close()
                    except Exception:
                        pass
            self._stop_evt.wait(4)

    def _resolve_port(self) -> str | None:
        if self.port and self.port != "auto":
            return self.port
        ports = list_serial_ports()
        candidates = [p for p in ports if p.likely] or [
            p for p in ports if "bluetooth" not in p.description.lower()]
        for p in candidates:
            if self._stop_evt.is_set():
                return None
            if probe_port(p.device, self.baud):
                return p.device
        return None

    def _cmd(self, ser: serial.Serial, cmd: str, timeout: float = 3.0) -> str:
        ser.reset_input_buffer()
        ser.write((cmd + "\r").encode("ascii"))
        buf, end = b"", time.monotonic() + timeout
        while time.monotonic() < end:
            chunk = ser.read(256)
            if chunk:
                buf += chunk
                if _END.search(buf):
                    break
        return buf.decode("latin-1", "ignore")

    def _init_modem(self, ser: serial.Serial):
        for _ in range(4):
            if re.search(r"\bOK\b", self._cmd(ser, "AT", 1.5)):
                break
        else:
            raise RuntimeError("El módem no responde a comandos AT")
        self._cmd(ser, "ATE0", 1.5)
        self._cmd(ser, "AT+CMEE=1", 1.5)
        if "READY" not in self._cmd(ser, "AT+CPIN?", 3):
            raise RuntimeError("SIM no lista (sin SIM, con PIN o aún registrando)")
        self._cmd(ser, "AT+CMGF=1", 2)            # SMS en modo texto
        self._cmd(ser, 'AT+CSCS="GSM"', 2)
        self._cmd(ser, "AT+CSDH=0", 2)
        self._cmd(ser, 'AT+CPMS="SM","SM","SM"', 3)  # guardar/leer en la SIM
        self._cmd(ser, "AT+CNMI=2,1,0,0,0", 2)

    def _loop(self, ser: serial.Serial):
        last_csq, fails = 0.0, 0
        while not self._stop_evt.is_set():
            if time.monotonic() - last_csq > 20:
                self._update_signal(ser)
                last_csq = time.monotonic()
            raw = self._cmd(ser, 'AT+CMGL="ALL"', 10)
            if re.search(r"\r?\nOK\r?\n?", raw):
                fails = 0
                self._process(ser, parse_cmgl(raw))
            else:
                fails += 1
                if fails >= 3:
                    raise RuntimeError("El módem dejó de responder")
            self._stop_evt.wait(2)

    def _update_signal(self, ser: serial.Serial):
        m = re.search(r"\+CSQ:\s*(\d+)", self._cmd(ser, "AT+CSQ", 2))
        self.signal_changed.emit(csq_to_bars(int(m[1])) if m else 0)

    # ------------------------------------------------------------------ SMS handling
    def _process(self, ser: serial.Serial, msgs: list[Sms]):
        failed = []
        for m in msgs:
            if self.handler(m.sender, m.ts, m.text):
                self._delete(ser, m.index)
            else:
                failed.append(m)
        # SMS largos llegan en varias partes: probar a unir partes consecutivas del mismo remitente
        used: set[int] = set()
        for i, first in enumerate(failed):
            if i in used or "nequi" not in first.text.lower():
                continue
            combo = first.text
            for j in range(i + 1, min(i + 4, len(failed))):
                if failed[j].sender != first.sender:
                    break
                combo += failed[j].text
                if self.handler(first.sender, first.ts, combo):
                    for k in range(i, j + 1):
                        used.add(k)
                        self._delete(ser, failed[k].index)
                    break

    def _delete(self, ser: serial.Serial, index: int):
        try:
            self._cmd(ser, f"AT+CMGD={index}", 3)
        except Exception as exc:
            log.warning("No se pudo borrar el SMS %s: %s", index, exc)
