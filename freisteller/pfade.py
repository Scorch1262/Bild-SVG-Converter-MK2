"""Pfade für Ressourcen, Modelle und Einstellungen (Quellcode und exe)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def ist_exe() -> bool:
    return bool(getattr(sys, "frozen", False))


def programm_ordner() -> Path:
    """Ordner, in dem die exe bzw. app.py liegt."""
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


def modell_ordner() -> list[Path]:
    """Alle Ordner, in denen nach .onnx-Modellen gesucht wird.

    Reihenfolge: Ordner 'modelle' neben der exe (eigene Modelle),
    dann die in die exe eingebetteten Modelle.
    """
    kandidaten = [programm_ordner() / "modelle", ressource("modelle")]
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
    """INI-Datei neben der exe; falls dort nicht beschreibbar, in %APPDATA%."""
    neben = programm_ordner() / "Bild-Freisteller-MK1.ini"
    try:
        if neben.exists():
            if os.access(neben, os.W_OK):
                return neben
        elif os.access(neben.parent, os.W_OK):
            return neben
    except OSError:
        pass
    basis = Path(os.environ.get("APPDATA") or Path.home() / ".config")
    ziel = basis / "Bild-Freisteller-MK1"
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel / "Bild-Freisteller-MK1.ini"
