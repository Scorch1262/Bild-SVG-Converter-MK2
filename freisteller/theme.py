"""Farben und Qt-Stylesheet im Design der Dashboards."""

from __future__ import annotations

import sys

# Farbpalette der Dashboards
FENSTER = "#14171C"
FELD = "#0F1216"
KARTE = "#181C22"
KARTE_HOVER = "#1E232B"
LINIE = "#262B33"
TEXT = "#E6E9EE"
TEXT_GEDAEMPFT = "#8A92A0"
TEAL = "#35D0BA"
TEAL_DUNKEL = "#2AA897"
AMBER = "#FFB84D"
ROT = "#FF5C5C"
AUSWAHL = "#1D4943"
DUNKEL_SCHRIFT = "#0B0D10"

SCHRIFT = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"

_STYLESHEET_VORLAGE = """
* {{
    font-family: "{SCHRIFT}";
    font-size: 10pt;
    color: {TEXT};
}}
QMainWindow, QWidget#Hauptflaeche, QDialog {{
    background: {FENSTER};
}}
QToolTip {{
    background: {KARTE}; color: {TEXT}; border: 1px solid {LINIE};
    padding: 4px 6px; border-radius: 4px;
}}

/* Kopfzeile */
QFrame#Kopf {{
    background: {KARTE};
    border-bottom: 1px solid {LINIE};
}}
QLabel#Titel {{ font-size: 13pt; font-weight: 600; letter-spacing: 0.5px; }}
QLabel#Untertitel {{ color: {TEXT_GEDAEMPFT}; }}
QLabel#Punkt {{ color: {TEAL}; font-size: 14pt; }}
QLabel#Chip {{
    color: {TEXT_GEDAEMPFT}; background: {FELD}; border: 1px solid {LINIE};
    border-radius: 10px; padding: 2px 10px; font-size: 9pt;
}}
QLabel#ChipAktiv {{
    color: {TEAL}; background: {AUSWAHL}; border: 1px solid {TEAL_DUNKEL};
    border-radius: 10px; padding: 2px 10px; font-size: 9pt;
}}
QLabel#ChipArbeit {{
    color: {AMBER}; background: #2A2418; border: 1px solid #5A4520;
    border-radius: 10px; padding: 2px 10px; font-size: 9pt;
}}
QLabel#ChipFehler {{
    color: {ROT}; background: #2A1A1A; border: 1px solid #5A2A2A;
    border-radius: 10px; padding: 2px 10px; font-size: 9pt;
}}

/* Seitenleiste und Karten */
QScrollArea#Seitenleiste, QWidget#SeitenleisteInhalt {{
    background: {FENSTER}; border: none;
}}
QFrame#Karte {{
    background: {KARTE}; border: 1px solid {LINIE}; border-radius: 10px;
}}
QToolButton#KartenKopf {{
    background: transparent; border: none; text-align: left;
    font-weight: 600; padding: 2px 0px; color: {TEXT};
}}
QToolButton#KartenKopf:hover {{ color: {TEAL}; }}
QLabel#Gedaempft {{ color: {TEXT_GEDAEMPFT}; font-size: 9pt; }}
QLabel#Wert {{ color: {TEAL}; font-size: 9pt; min-width: 38px; }}
QLabel#Hinweis {{ color: {AMBER}; font-size: 9pt; }}

/* Schaltflächen */
QPushButton {{
    background: {FELD}; border: 1px solid {LINIE}; border-radius: 6px;
    padding: 6px 12px;
}}
QPushButton:hover {{ border-color: {TEAL}; color: {TEAL}; }}
QPushButton:pressed {{ background: {AUSWAHL}; }}
QPushButton:disabled {{ color: #4A515C; border-color: {LINIE}; }}
QPushButton:checked {{
    background: {AUSWAHL}; border-color: {TEAL}; color: {TEAL};
}}
QPushButton#Primaer {{
    background: {TEAL}; color: {DUNKEL_SCHRIFT}; border: 1px solid {TEAL};
    font-weight: 600;
}}
QPushButton#Primaer:hover {{ background: #4FE0CB; color: {DUNKEL_SCHRIFT}; }}
QPushButton#Primaer:pressed {{ background: {TEAL_DUNKEL}; }}
QPushButton#Primaer:disabled {{
    background: #24443F; color: #5E7A75; border-color: #24443F;
}}
QPushButton#Farbe {{ min-width: 28px; max-width: 28px; padding: 0px; min-height: 24px; }}

/* Segment-Auswahl */
QPushButton#Segment {{
    border-radius: 0px; padding: 5px 10px; background: {FELD};
}}
QPushButton#Segment:checked {{
    background: {TEAL}; color: {DUNKEL_SCHRIFT}; border-color: {TEAL};
}}
QPushButton#SegmentLinks {{ border-top-left-radius: 6px; border-bottom-left-radius: 6px; }}

/* Eingaben */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: {FELD}; border: 1px solid {LINIE}; border-radius: 6px;
    padding: 4px 8px; selection-background-color: {AUSWAHL};
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: {TEAL_DUNKEL}; }}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {TEAL}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url("{PFEIL}"); width: 10px; height: 6px; }}
QComboBox::down-arrow:hover, QComboBox::down-arrow:on {{ image: url("{PFEIL_TEAL}"); }}
QComboBox QAbstractItemView {{
    background: {KARTE}; border: 1px solid {LINIE}; outline: none;
    selection-background-color: {AUSWAHL}; selection-color: {TEAL}; padding: 4px;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1px solid {LINIE};
    border-radius: 4px; background: {FELD};
}}
QCheckBox::indicator:hover {{ border-color: {TEAL}; }}
QCheckBox::indicator:checked {{ background: {TEAL}; border-color: {TEAL}; }}

QSlider::groove:horizontal {{
    height: 4px; background: {LINIE}; border-radius: 2px;
}}
QSlider::sub-page:horizontal {{ background: {TEAL_DUNKEL}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {TEAL}; width: 14px; height: 14px; margin: -6px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: #6AEAD7; }}

QProgressBar {{
    background: {FELD}; border: 1px solid {LINIE}; border-radius: 4px;
    height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {TEAL}; border-radius: 3px; }}

/* Bildansicht */
QGraphicsView {{ background: {FELD}; border: 1px solid {LINIE}; border-radius: 10px; }}

/* Statusleiste */
QStatusBar {{
    background: {KARTE}; border-top: 1px solid {LINIE}; color: {TEXT_GEDAEMPFT};
}}
QStatusBar QLabel {{ color: {TEXT_GEDAEMPFT}; font-size: 9pt; }}

QScrollBar:vertical {{ background: {FENSTER}; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {LINIE}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {TEAL_DUNKEL}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: {FENSTER}; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {LINIE}; border-radius: 5px; min-width: 30px; }}

QMessageBox {{ background: {FENSTER}; }}
QMenu {{
    background: {KARTE}; border: 1px solid {LINIE}; padding: 4px;
}}
QMenu::item {{ padding: 6px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {AUSWAHL}; color: {TEAL}; }}
"""


def _stylesheet() -> str:
    from .pfade import ressource

    werte = dict(globals())
    werte["PFEIL"] = ressource("assets", "pfeil.png").as_posix()
    werte["PFEIL_TEAL"] = ressource("assets", "pfeil_teal.png").as_posix()
    return _STYLESHEET_VORLAGE.format(**werte)


STYLESHEET = _stylesheet()


def dunkle_titelleiste(fenster) -> None:
    """Schaltet unter Windows 10/11 die dunkle Titelleiste ein."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(fenster.winId())
        wert = ctypes.c_int(1)
        for attribut in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (neu/alt)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribut, ctypes.byref(wert), ctypes.sizeof(wert)) == 0:
                break
        # Windows 11: Titelleistenfarbe wie das Fenster (COLORREF = 0x00BBGGRR)
        farbe = ctypes.c_int(0x001C1714)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(farbe), ctypes.sizeof(farbe))
    except Exception:
        pass
