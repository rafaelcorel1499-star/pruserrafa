from __future__ import annotations

import re
import sqlite3
import threading
from datetime import date, datetime

from sms_parser import ParsedPayment

SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sms_key TEXT UNIQUE,
    business TEXT,
    sender TEXT NOT NULL,
    amount REAL NOT NULL,
    paid_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    channel TEXT,
    raw TEXT
);
CREATE INDEX IF NOT EXISTS idx_paid_at ON payments(paid_at);
"""


class Database:
    def __init__(self, path):
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def add_payment(self, p: ParsedPayment, sms_key: str):
        """Devuelve el pago como dict, o None si ya existía (duplicado)."""
        with self.lock:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO payments(sms_key,business,sender,amount,paid_at,received_at,channel,raw)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (sms_key, p.business, p.sender, p.amount, p.paid_at.isoformat(timespec="seconds"),
                 datetime.now().isoformat(timespec="seconds"), p.channel, p.raw),
            )
            self.conn.commit()
            if cur.rowcount == 0:
                return None
            row = self.conn.execute("SELECT * FROM payments WHERE id=?", (cur.lastrowid,)).fetchone()
            return dict(row)

    def query(self, text="", d_from: date | None = None, d_to: date | None = None,
              amin: float | None = None, amax: float | None = None, limit: int | None = None):
        sql, args = "SELECT * FROM payments WHERE 1=1", []
        text = (text or "").strip()
        if text:
            digits = re.sub(r"[\$\.,\s]", "", text)
            if digits.isdigit():
                sql += " AND (sender LIKE ? OR CAST(CAST(amount AS INTEGER) AS TEXT) LIKE ?)"
                args += [f"%{text}%", f"%{digits}%"]
            else:
                sql += " AND sender LIKE ?"
                args.append(f"%{text}%")
        if d_from:
            sql += " AND date(paid_at) >= ?"
            args.append(d_from.isoformat())
        if d_to:
            sql += " AND date(paid_at) <= ?"
            args.append(d_to.isoformat())
        if amin is not None:
            sql += " AND amount >= ?"
            args.append(amin)
        if amax is not None:
            sql += " AND amount <= ?"
            args.append(amax)
        sql += " ORDER BY paid_at DESC, id DESC"
        if limit:
            sql += f" LIMIT {int(limit)}"
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def stats_today(self):
        today = date.today().isoformat()
        with self.lock:
            count, total = self.conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM payments WHERE date(paid_at)=?", (today,)
            ).fetchone()
            last = self.conn.execute(
                "SELECT amount FROM payments ORDER BY paid_at DESC, id DESC LIMIT 1"
            ).fetchone()
        return count, total, (last[0] if last else None)
