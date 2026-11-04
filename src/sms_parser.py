"""Lee el SMS de Nequi y extrae negocio, valor, remitente, fecha/hora y canal.

Ejemplo:
  notificacion Nequi: el negocio PORTAWARE recibio $200 de RAFAEL HERNANDO
  SANCHEZ CAMPO el 25/10/2026 a las 02:08 a.m a travez de  Bre-B.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

_PATTERN = re.compile(
    r"nequi\s*:\s*el\s+negocio\s+(?P<business>.+?)\s+recib[ií][oó]\s+\$\s*(?P<amount>\d[\d.,]*)"
    r"\s+de\s+(?P<sender>.+?)\s+el\s+(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+a\s+las\s+"
    r"(?P<time>\d{1,2}:\d{2})(?::\d{2})?\s*(?:(?P<ampm>[ap])\s*\.?\s*m\.?)?"
    r"(?:\s+a\s+tra\w*\s+de\s+(?P<channel>[^.]+?)\s*(?:\.|$))?",
    re.IGNORECASE,
)

_PARTICLES = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "SAN", "SANTA"}


@dataclass
class ParsedPayment:
    business: str
    amount: float
    sender: str
    paid_at: datetime
    channel: str
    raw: str


def parse_amount(text: str) -> float:
    """'200' -> 200 ; '1.000' -> 1000 ; '1,000' -> 1000 ; '1.000,50' -> 1000.5"""
    s = re.sub(r"[^\d.,]", "", text).strip(".,")
    if not s:
        raise ValueError("monto vacío")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        parts = s.split(sep)
        if len(parts) > 2 or len(parts[-1]) == 3:
            s = "".join(parts)
        else:
            s = parts[0] + "." + parts[1]
    return float(s)


def parse_sms(text: str) -> Optional[ParsedPayment]:
    clean = unicodedata.normalize("NFKC", text or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    m = _PATTERN.search(clean)
    if not m:
        return None
    try:
        amount = parse_amount(m["amount"])
    except ValueError:
        return None

    now = datetime.now()
    try:
        day, month, year = (int(x) for x in m["date"].split("/"))
        hour, minute = (int(x) for x in m["time"].split(":"))
        ampm = (m["ampm"] or "").lower()
        if ampm:
            hour = hour % 12 + (12 if ampm == "p" else 0)
        paid_at = datetime(year, month, day, hour, minute)
    except ValueError:
        paid_at = now.replace(second=0, microsecond=0)

    return ParsedPayment(
        business=m["business"].strip(),
        amount=amount,
        sender=m["sender"].strip().upper(),
        paid_at=paid_at,
        channel=(m["channel"] or "").strip(),
        raw=clean,
    )


def short_name(full: str) -> str:
    """'RAFAEL HERNANDO SANCHEZ CAMPO' -> 'Rafael Sanchez' (primer nombre + primer apellido)."""
    tokens = full.split()
    merged, buf = [], []
    for t in tokens:
        if t.upper() in _PARTICLES:
            buf.append(t)
        else:
            merged.append(" ".join(buf + [t]))
            buf = []
    if buf:
        merged.append(" ".join(buf))
    if not merged:
        return ""
    if len(merged) <= 2:
        chosen = merged
    elif len(merged) == 3:
        chosen = [merged[0], merged[2]]   # NOMBRE + APELLIDO1 APELLIDO2 / NOMBRE1 NOMBRE2 APELLIDO
    else:
        chosen = [merged[0], merged[2]]   # N1 N2 A1 A2 -> N1 A1
    name = " ".join(chosen)
    # Solo letras y espacios: este texto se lee en voz alta
    name = re.sub(r"[^\w\s]|\d|_", "", name)
    return name.title()


DEFAULT_TEMPLATE = "Recibiste un pago con valor {valor} pesos de {nombre}"
MAX_TEMPLATE_LEN = 160
PLACEHOLDERS = ("{valor}", "{nombre}")


def validate_template(template: str) -> Optional[str]:
    """Devuelve None si la plantilla es válida o un texto explicando el problema."""
    t = template or ""
    if len(t.strip()) > MAX_TEMPLATE_LEN:
        return f"El mensaje es muy largo (máximo {MAX_TEMPLATE_LEN} caracteres)."
    missing = [p for p in PLACEHOLDERS if p not in t]
    if missing:
        return "El mensaje debe incluir " + " y ".join(missing) + " (son datos del pago y no se pueden quitar)."
    leftovers = t.replace("{valor}", "").replace("{nombre}", "")
    if "{" in leftovers or "}" in leftovers:
        return "Solo se permiten las marcas {valor} y {nombre}; no uses otras llaves { }."
    return None


def render_message(template: str, amount: float, sender: str) -> str:
    """Arma el texto que se dice en voz alta. Si la plantilla no es válida usa la original."""
    if validate_template(template) is not None:
        template = DEFAULT_TEMPLATE
    if float(amount).is_integer():
        value = str(int(amount))
    else:
        value = f"{amount:.2f}".replace(".", " con ")
    text = template.replace("{valor}", value).replace("{nombre}", short_name(sender))
    return re.sub(r"\s+", " ", text).strip()


def spoken_phrase(amount: float, sender: str, template: str = DEFAULT_TEMPLATE) -> str:
    return render_message(template, amount, sender)


def format_money(amount: float) -> str:
    return f"${amount:,.0f}" if float(amount).is_integer() else f"${amount:,.2f}"


def format_date(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y")


def format_time(dt: datetime) -> str:
    return dt.strftime("%I:%M ") + ("a.m" if dt.hour < 12 else "p.m")
