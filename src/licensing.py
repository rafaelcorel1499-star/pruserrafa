"""Licencias de NequiPay Monitor.

Cada PC tiene un ID (derivado del MachineGuid de Windows). El administrador, con el programa
NequiPayKeygen, firma ese ID con su llave PRIVADA (Ed25519) y entrega el resultado como serial.
La app solo contiene la llave PÚBLICA: puede comprobar un serial, pero no puede crear nuevos.
El serial solo es válido en el PC cuyo ID fue firmado.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import uuid
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app_paths import data_dir
from license_pub import PUBLIC_KEY_HEX

_SIGN_PREFIX = b"NEQUIPAY-LICENSE-v1|"
_ID_ALPHABET = re.compile(r"[A-Z2-7]{16}")


# ---------------------------------------------------------------------- ID del equipo
def _raw_machine_guid() -> str:
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                                0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                return str(winreg.QueryValueEx(key, "MachineGuid")[0])
        except OSError:
            pass
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                v = f.read().strip()
            if v:
                return v
        except OSError:
            continue
    return f"mac-{uuid.getnode():012x}"


def group(text: str, size: int = 4) -> str:
    return "-".join(text[i:i + size] for i in range(0, len(text), size))


def machine_id() -> str:
    """ID corto y estable de este PC, p. ej. 'K7QD-2XHM-PA4T-7RWB' (se lo das al administrador)."""
    digest = hashlib.sha256(b"NEQUIPAY-PC|" + _raw_machine_guid().encode("utf-8")).digest()
    return group(base64.b32encode(digest[:10]).decode("ascii"))


def normalize_pc_id(text: str) -> Optional[str]:
    """Acepta el ID con o sin guiones/espacios y en minúsculas. Devuelve None si no es válido."""
    s = re.sub(r"[\s\-]", "", text or "").upper()
    return group(s) if _ID_ALPHABET.fullmatch(s) else None


# ---------------------------------------------------------------------- serial
def sign_payload(pc_id: str) -> bytes:
    norm = normalize_pc_id(pc_id)
    if norm is None:
        raise ValueError("ID de equipo no válido")
    return _SIGN_PREFIX + norm.replace("-", "").encode("ascii")


def format_serial(signature: bytes) -> str:
    return group(base64.b32encode(signature).decode("ascii").rstrip("="), 5)


def parse_serial(text: str) -> Optional[bytes]:
    s = re.sub(r"[\s\-]", "", text or "").upper()
    if not s or not re.fullmatch(r"[A-Z2-7]+", s):
        return None
    try:
        return base64.b32decode(s + "=" * (-len(s) % 8))
    except ValueError:
        return None


def verify_serial(serial: str, pc_id: Optional[str] = None, public_key_hex: Optional[str] = None) -> bool:
    sig = parse_serial(serial)
    if sig is None or len(sig) != 64:
        return False
    try:
        payload = sign_payload(pc_id or machine_id())
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex or PUBLIC_KEY_HEX))
        key.verify(sig, payload)
        return True
    except (InvalidSignature, ValueError):
        return False


# ---------------------------------------------------------------------- almacenamiento local
def _license_path():
    return data_dir() / "license.json"


def saved_serial() -> str:
    try:
        with open(_license_path(), "r", encoding="utf-8") as f:
            return str(json.load(f).get("serial", ""))
    except (OSError, ValueError, AttributeError):
        return ""


def save_serial(serial: str) -> None:
    tmp = str(_license_path()) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"serial": serial.strip()}, f, indent=2)
    os.replace(tmp, _license_path())


def is_activated() -> bool:
    s = saved_serial()
    return bool(s) and verify_serial(s)
