"""Crea un par de llaves nuevo (solo si quieres cambiar el actual).

  python tools/new_keypair.py

- keygen/private.key  -> llave PRIVADA. Solo para el administrador. NUNCA la subas a GitHub ni la compartas.
- src/license_pub.py  -> llave pública que va dentro de la app.

OJO: al cambiar de llaves, los seriales ya entregados dejan de funcionar con la app nueva.
"""
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent
PRIV = ROOT / "keygen" / "private.key"
PUB = ROOT / "src" / "license_pub.py"

if PRIV.exists() and "--force" not in sys.argv:
    sys.exit(f"Ya existe {PRIV}. Si de verdad quieres reemplazarla (invalida los seriales entregados): "
             f"python tools/new_keypair.py --force")

key = Ed25519PrivateKey.generate()
PRIV.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()))
raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
PUB.write_text('"""Llave pública de licencias (generada con tools/new_keypair.py). No es secreta."""\n'
               f'PUBLIC_KEY_HEX = "{raw.hex()}"\n', encoding="utf-8")
print("Listo.\n  Llave privada:", PRIV, "\n  Llave pública:", PUB)
