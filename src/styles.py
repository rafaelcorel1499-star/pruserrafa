from __future__ import annotations

import re

from PySide6.QtGui import QColor


class _Theme:
    primary = "#8B1FE8"
    secondary = "#FFFFFF"


THEME = _Theme()


def valid_hex(s: str) -> bool:
    return bool(re.fullmatch(r"#?[0-9a-fA-F]{6}", (s or "").strip()))


def norm_hex(s: str) -> str:
    return "#" + s.strip().lstrip("#").upper()


def mix(a: str, b: str, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    return QColor(round(ca.red() + (cb.red() - ca.red()) * t),
                  round(ca.green() + (cb.green() - ca.green()) * t),
                  round(ca.blue() + (cb.blue() - ca.blue()) * t))


def build_stylesheet(primary: str, secondary: str) -> str:
    P, S = primary, secondary
    dark = mix(P, "#000000", 0.38).name()
    hover = mix(P, "#000000", 0.14).name()
    card = mix(P, "#FFFFFF", 0.90).name()
    soft = mix(P, "#FFFFFF", 0.95).name()
    bg = mix(P, "#FFFFFF", 0.965).name()
    border = mix(P, "#FFFFFF", 0.78).name()
    ink = mix(P, "#000000", 0.62).name()
    muted = mix(P, "#808080", 0.45).name()
    return f"""
QWidget#root, QWidget#page {{ background: {bg}; }}
QLabel {{ color: {ink}; background: transparent; }}
#header {{ background: white; border-bottom: 1px solid {border}; }}
QLabel#appTitle {{ font-size: 26px; font-weight: 800; color: {ink}; }}
QLabel#bizName {{ font-size: 12px; color: {muted}; font-weight: 600; }}
QLabel#clock {{ font-size: 15px; font-weight: 600; color: {ink}; }}
QFrame#vsep {{ background: {border}; max-width: 1px; min-width: 1px; }}
QLabel#status {{ border-radius: 14px; padding: 8px 16px; font-weight: 700; }}
QLabel#status[ok="true"] {{ background: #DCFCE7; color: #166534; }}
QLabel#status[ok="false"] {{ background: #FEE2E2; color: #991B1B; }}
QPushButton#gear {{ background: {P}; border: none; border-radius: 24px; min-width: 48px; max-width: 48px; min-height: 48px; max-height: 48px; }}
QPushButton#gear:hover {{ background: {hover}; }}

#sidebar {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {P}, stop:1 {dark}); }}
#sidebar QLabel {{ color: {S}; }}
QFrame#sidebarLine {{ background: rgba(255,255,255,70); max-height: 1px; min-height: 1px; }}
QPushButton#nav {{ background: transparent; color: {S}; border: none; border-radius: 14px;
    padding: 13px 16px; text-align: left; font-size: 16px; font-weight: 700; }}
QPushButton#nav:hover {{ background: rgba(255,255,255,45); }}
QPushButton#nav:checked {{ background: {S}; color: {P}; }}

QFrame#card {{ background: {card}; border: 1px solid {border}; border-radius: 18px; }}
QFrame#panel {{ background: white; border: 1px solid {border}; border-radius: 18px; }}
QFrame#bottombar {{ background: white; border-top: 1px solid {border}; }}
QLabel#cardTitle {{ font-size: 16px; color: {muted}; font-weight: 500; }}
QLabel#cardValue {{ font-size: 28px; font-weight: 800; color: {ink}; }}
QLabel#iconCircle {{ background: {P}; color: {S}; border-radius: 29px; min-width: 58px; max-width: 58px;
    min-height: 58px; max-height: 58px; font-size: 24px; font-weight: 700; }}
QLabel#iconAccent {{ color: {P}; }}
QLabel#h1 {{ font-size: 30px; font-weight: 800; color: {ink}; }}
QLabel#h3 {{ font-size: 19px; font-weight: 800; color: {ink}; }}
QLabel#fieldLabel {{ font-size: 15px; font-weight: 600; color: {ink}; }}
QLabel#muted {{ color: {muted}; }}
QLabel#statePill {{ border-radius: 12px; padding: 4px 16px; font-weight: 800; font-size: 17px; color: white; }}
QLabel#statePill[ok="true"] {{ background: #16A34A; }}
QLabel#statePill[ok="false"] {{ background: #DC2626; }}
QLabel#chip {{ background: #DCFCE7; color: #166534; border-radius: 13px; padding: 3px 12px; font-weight: 600; }}
QFrame#accentBar {{ background: {P}; border-radius: 3px; min-width: 6px; max-width: 6px; min-height: 26px; max-height: 26px; }}

QLineEdit, QPlainTextEdit, QComboBox, QDateEdit {{ background: white; border: 1px solid {border}; border-radius: 11px;
    padding: 8px 12px; min-height: 22px; color: {ink}; selection-background-color: {P}; selection-color: {S}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus {{ border: 1px solid {P}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 30px; }}
QComboBox QAbstractItemView {{ background: white; color: {ink}; border: 1px solid {border};
    selection-background-color: {P}; selection-color: {S}; outline: 0; }}

QPushButton#primary {{ background: {P}; color: {S}; border: none; border-radius: 13px; padding: 11px 24px;
    font-weight: 700; font-size: 15px; }}
QPushButton#primary:hover {{ background: {hover}; }}
QPushButton#ghost {{ background: white; color: {ink}; border: 2px solid {P}; border-radius: 13px;
    padding: 10px 28px; font-weight: 700; font-size: 15px; }}
QPushButton#ghost:hover {{ background: {soft}; }}
QPushButton#small {{ background: white; color: {ink}; border: 1px solid {border}; border-radius: 11px;
    padding: 7px 14px; font-weight: 600; }}
QPushButton#small:hover {{ background: {soft}; border-color: {P}; }}
QPushButton#link {{ background: transparent; color: {P}; border: none; font-weight: 700; padding: 6px 8px; }}
QPushButton#link:hover {{ color: {hover}; }}

QTableWidget {{ background: white; border: none; outline: 0; alternate-background-color: {soft}; color: {ink}; }}
QTableWidget::item {{ padding: 4px 12px; border: none; }}
QHeaderView::section {{ background: {card}; color: {ink}; border: none; padding: 11px 12px;
    font-weight: 800; font-size: 15px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QSlider::groove:horizontal {{ height: 6px; background: {border}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {P}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; border: 3px solid {P}; width: 14px; height: 14px;
    margin: -8px 0; border-radius: 10px; }}
QCheckBox {{ color: {ink}; spacing: 10px; font-weight: 600; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 6px; border: 2px solid {P}; background: white; }}
QCheckBox::indicator:checked {{ background: {P}; }}

QFrame#dropZone {{ border: 2px dashed {P}; border-radius: 14px; background: {soft}; }}
QFrame#logoBox {{ border: 1px solid {border}; border-radius: 14px; background: white; }}
QFrame#toast {{ background: #16A34A; border-radius: 14px; }}
QFrame#toast QLabel {{ color: white; font-weight: 700; font-size: 15px; background: transparent; }}
QPushButton#toastClose {{ background: transparent; color: white; border: none; font-size: 20px; padding: 0 6px; }}
QToolTip {{ background: white; color: {ink}; border: 1px solid {border}; padding: 4px 8px; }}
"""
