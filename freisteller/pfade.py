"""Pfade für Ressourcen, Modelle und Einstellungen.

Die exe legt NICHTS neben sich ab. Einstellungen und eigene Modelle
liegen im Benutzerordner:
    Windows:  %APPDATA%\\Bild-SVG-Converter-MK2\\
    sonst:    ~/.config/Bild-SVG-Converter-MK2/
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .version import APP_NAME


def ist_exe() -> bool:
    return bool(getattr(sys, "frozen", False))


def programm_ordner() -> Path:
    """Ordner, in dem die exe bzw. app.py liegt (wird nur gelesen)."""
    if ist_exe():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def ressourcen_ordner() -> Path:
    """Ordner mit eingebetteten Dateien (bei PyInstaller: _MEIPASS)."""
    if ist_exe() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


def ressource(*teile: str) -> Path:
    return ressourcen_ordner().joinpath(*teile)


def benutzer_ordner(anlegen: bool = True) -> Path:
    """Eigener Ordner im Benutzerprofil für Einstellungen und Modelle."""
    basis = os.environ.get("APPDATA")
    ordner = Path(basis) / APP_NAME if basis else Path.home() / ".config" / APP_NAME
    if anlegen:
        try:
            ordner.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return ordner


def eigene_modelle_ordner() -> Path:
    """Ordner für zusätzliche .onnx-Modelle (im Benutzerordner)."""
    return benutzer_ordner(anlegen=False) / "modelle"


def modell_ordner() -> list[Path]:
    """Alle Ordner, in denen nach .onnx-Modellen gesucht wird.

    Reihenfolge: eigene Modelle im Benutzerordner, dann die in die exe
    eingebetteten Modelle (bzw. beim Quellcode der Ordner 'modelle').
    """
    kandidaten = [eigene_modelle_ordner(), ressource("modelle")]
    gesehen: list[Path] = []
    for k in kandidaten:
        try:
            k = k.resolve()
        except OSError:
            continue
        if k not in gesehen and k.is_dir():
            gesehen.append(k)
    return gesehen


def einstellungen_datei() -> Path:
    """INI-Datei im Benutzerordner.

    Eine INI aus v2.0.0, die noch neben der exe liegt, wird einmalig
    in den Benutzerordner verschoben, damit neben der exe nichts bleibt.
    """
    ziel = benutzer_ordner() / f"{APP_NAME}.ini"
    alt = programm_ordner() / f"{APP_NAME}.ini"
    if ist_exe() and alt.is_file() and not ziel.exists():
        try:
            shutil.move(str(alt), str(ziel))
        except OSError:
            pass
    return ziel
