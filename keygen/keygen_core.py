"""Lógica del generador de seriales (sin interfaz): cargar la llave privada y firmar IDs de equipo."""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from licensing import format_serial, normalize_pc_id, sign_payload


def base_dir() -> Path:
    """Carpeta del .exe (o de este archivo en desarrollo): ahí se busca private.key y se guarda el historial."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_private_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("El archivo no es una llave privada válida de NequiPay")
    return key


def generate_serial(key: Ed25519PrivateKey, pc_id: str) -> str:
    norm = normalize_pc_id(pc_id)
    if norm is None:
        raise ValueError("El ID del equipo no es válido. Debe tener 16 caracteres (letras A-Z y números 2-7), "
                         "por ejemplo K7QD-2XHM-PA4T-7RWB.")
    return format_serial(key.sign(sign_payload(norm)))


def log_issued(folder: Path, client: str, pc_id: str, serial: str) -> None:
    """Guarda un registro de cada serial entregado (seriales_emitidos.csv junto al programa)."""
    path = Path(folder) / "seriales_emitidos.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["fecha", "cliente", "id_equipo", "serial"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), client, normalize_pc_id(pc_id), serial])
