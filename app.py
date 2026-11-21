"""Bild-Freisteller-MK1 – Startdatei.

Aufruf:
    Bild-Freisteller-MK1.exe [bild]       Programm starten (optional mit Bild)
    Bild-Freisteller-MK1.exe --selftest   Funktionstest ohne Fenster (Exit-Code 0 = ok)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def _selbsttest() -> int:
    """Prüft KI-Freistellung, Farb-Freistellung, Nachbearbeitung und SVG-Export."""
    from PIL import Image, ImageDraw
    import numpy as np

    from freisteller import maske as mk
    from freisteller import segmentierung as seg
    from freisteller import svg_export as svgx
    from freisteller.version import APP_NAME, APP_VERSION

    zeilen: list[str] = [f"{APP_NAME} v{APP_VERSION} – Selbsttest"]
    ok = True

    def pruefe(name: str, bedingung: bool, info: str = "") -> None:
        nonlocal ok
        ok &= bool(bedingung)
        zeilen.append(f"[{'OK ' if bedingung else 'FEHLER'}] {name} {info}".rstrip())

    # Testbild: rote Scheibe mit gelbem Rechteck auf weißem Grund
    bild = Image.new("RGB", (640, 480), (255, 255, 255))
    d = ImageDraw.Draw(bild)
    d.ellipse((170, 90, 470, 390), fill=(220, 50, 40))
    d.rectangle((280, 200, 360, 280), fill=(250, 200, 30))
    soll = np.zeros((480, 640), bool)
    yy, xx = np.mgrid[0:480, 0:640]
    soll |= ((xx - 320) / 150.0) ** 2 + ((yy - 240) / 150.0) ** 2 <= 1.0

    # Farbe
    m = seg.farb_maske(bild, seg.rand_farbe(bild), 10, True, 0)
    treffer = ((m > 0.5) == soll).mean()
    pruefe("Freistellen nach Farbe", treffer > 0.995, f"({treffer * 100:.2f} % korrekt)")

    # KI
    modelle = seg.modelle_finden()
    pruefe("KI-Modell vorhanden", bool(modelle),
           f"({', '.join(m.name for m in modelle) or 'keins'})")
    if modelle:
        t = time.perf_counter()
        km = seg.KiFreisteller().maske(bild, modelle[0])
        dauer = time.perf_counter() - t
        treffer = ((km > 0.5) == soll).mean()
        pruefe("Freistellen mit KI", treffer > 0.97,
               f"({treffer * 100:.2f} % korrekt, {dauer:.1f} s)")

    # Nachbearbeitung + Pinsel
    e = mk.MaskenEinstellungen(kante_px=-2, glaetten_px=1.0, inseln_px=50,
                               loecher_fuellen=True)
    p = mk.PinselEbene(640, 480)
    p.strich_beginnen()
    p.tupfen(10, 10, 60, 10, 5, 1)
    p.strich_beenden()
    mm = mk.maske_bearbeiten(m, e, p.daten)
    pruefe("Nachbearbeitung + Pinsel", mm[10, 30] == 1.0 and mm[240, 320] > 0.99)
    pruefe("Rückgängig", p.rueckgaengig() and not p.daten.any())

    # Export
    erg = mk.zuschneiden(mk.ergebnis_bild(bild, mk.maske_bearbeiten(m, e)), 0)
    pruefe("Zuschneiden", abs(erg.width - 297) <= 6 and abs(erg.height - 297) <= 6,
           f"({erg.width}×{erg.height})")
    for art in svgx.ARTEN:
        svg = svgx.svg_erzeugen(erg, svgx.SvgEinstellungen(art=art))
        gut = svg.lstrip().startswith("<?xml") and "</svg>" in svg
        if art != "pixel":
            gut &= svgx.svg_pfade_zaehlen(svg) > 0
        pruefe(f"SVG {art}", gut, f"({len(svg)} Zeichen)")

    # Qt-Oberfläche ohne Anzeige aufbauen
    try:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from freisteller.hauptfenster import Hauptfenster
        from freisteller.theme import STYLESHEET
        app = QApplication.instance() or QApplication(sys.argv)
        app.setStyleSheet(STYLESHEET)
        f = Hauptfenster()
        pruefe("Oberfläche", f is not None)
    except Exception as exc:  # noqa: BLE001
        pruefe("Oberfläche", False, str(exc))

    zeilen.append("ERGEBNIS: " + ("BESTANDEN" if ok else "FEHLGESCHLAGEN"))
    text = "\n".join(zeilen)
    if sys.stdout is not None:  # in der Fenster-exe gibt es keine Konsole
        print(text)
    try:
        from freisteller.pfade import programm_ordner
        (programm_ordner() / "selbsttest.log").write_text(text + "\n", encoding="utf-8")
    except OSError:
        pass
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return _selbsttest()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from freisteller.hauptfenster import Hauptfenster
    from freisteller.pfade import ressource
    from freisteller.theme import STYLESHEET
    from freisteller.version import APP_NAME, APP_VERSION

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                f"Scorch1262.{APP_NAME}.{APP_VERSION}")
        except Exception:
            pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    icon = ressource("assets", "icon.ico")
    if not icon.exists():
        icon = ressource("assets", "icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    fenster = Hauptfenster()
    fenster.show()

    argumente = [a for a in sys.argv[1:] if not a.startswith("--")]
    if argumente and Path(argumente[0]).is_file():
        fenster.bild_laden(argumente[0])

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
