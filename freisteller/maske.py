"""Nachbearbeitung der Maske, Pinsel-Korrekturen und Ergebnisbild."""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from PIL import Image
from scipy import ndimage

_KREUZ = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)


@dataclass
class MaskenEinstellungen:
    schwelle: int = 50            # 0..100 %
    weiche_kanten: bool = True    # KI-Alpha am Rand übernehmen
    kante_px: int = 0             # <0 verkleinern, >0 erweitern
    glaetten_px: float = 0.0      # Weichzeichnen der Kante
    inseln_px: int = 0            # kleinere Motiv-Inseln entfernen
    loecher_fuellen: bool = False # Löcher im Motiv schließen

    def als_dict(self) -> dict:
        return asdict(self)


def _wachsen(m: np.ndarray, schritte: int, groesser: bool) -> np.ndarray:
    """Erweitert/verkleinert die Maske um `schritte` Pixel (annähernd rund)."""
    f = ndimage.grey_dilation if groesser else ndimage.grey_erosion
    for i in range(schritte):
        if i % 2 == 0:
            m = f(m, footprint=_KREUZ)
        else:
            m = f(m, size=(3, 3))
    return m


def maske_bearbeiten(
    grund: np.ndarray,
    e: MaskenEinstellungen,
    pinsel: np.ndarray | None = None,
) -> np.ndarray:
    """Wendet die Einstellungen auf die Grundmaske an (float32 0..1)."""
    m = grund.astype(np.float32, copy=True)
    t = e.schwelle / 100.0

    if e.weiche_kanten:
        lo, hi = t - 0.25, t + 0.25
        m = np.clip((m - lo) / (hi - lo), 0.0, 1.0)
    else:
        m = (m >= t).astype(np.float32)

    if e.inseln_px > 0 or e.loecher_fuellen:
        binaer = m >= 0.5
        if e.inseln_px > 0:
            beschr, anzahl = ndimage.label(binaer)
            if anzahl:
                groessen = np.bincount(beschr.ravel())
                klein = groessen < e.inseln_px
                klein[0] = False
                weg = klein[beschr]
                m[weg] = 0.0
                binaer &= ~weg
        if e.loecher_fuellen:
            gefuellt = ndimage.binary_fill_holes(binaer)
            m[gefuellt & ~binaer] = 1.0

    if e.kante_px:
        m = _wachsen(m, abs(int(e.kante_px)), e.kante_px > 0)

    if e.glaetten_px > 0:
        m = ndimage.gaussian_filter(m, sigma=float(e.glaetten_px) / 2.0)

    if pinsel is not None:
        m[pinsel > 0] = 1.0
        m[pinsel < 0] = 0.0

    return np.clip(m, 0.0, 1.0).astype(np.float32)


def ergebnis_bild(original: Image.Image, maske: np.ndarray) -> Image.Image:
    """Original mit Maske als Alphakanal (RGBA)."""
    rgba = np.array(original.convert("RGBA"), dtype=np.uint8)
    alpha = rgba[..., 3].astype(np.float32) * maske
    rgba[..., 3] = np.clip(alpha + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def inhalt_rahmen(bild: Image.Image, rand_px: int = 0) -> tuple[int, int, int, int] | None:
    """Begrenzungsrahmen der sichtbaren Pixel (links, oben, rechts, unten)."""
    alpha = np.asarray(bild.getchannel("A"))
    ys, xs = np.nonzero(alpha > 4)
    if len(xs) == 0:
        return None
    w, h = bild.size
    return (
        max(int(xs.min()) - rand_px, 0),
        max(int(ys.min()) - rand_px, 0),
        min(int(xs.max()) + 1 + rand_px, w),
        min(int(ys.max()) + 1 + rand_px, h),
    )


def zuschneiden(bild: Image.Image, rand_px: int = 0) -> Image.Image:
    r = inhalt_rahmen(bild, rand_px)
    return bild.crop(r) if r else bild


class PinselEbene:
    """Pinsel-Korrekturen: +1 = behalten, -1 = entfernen, 0 = unverändert.

    Rückgängig/Wiederholen speichert nur den geänderten Bildausschnitt.
    """

    MAX_SCHRITTE = 40

    def __init__(self, breite: int, hoehe: int) -> None:
        self.daten = np.zeros((hoehe, breite), np.int8)
        self._rueck: list[tuple] = []
        self._vor: list[tuple] = []
        self._vorher: np.ndarray | None = None
        self._rahmen: list[int] | None = None

    # -- Strich ----------------------------------------------------------
    def strich_beginnen(self) -> None:
        self._vorher = self.daten.copy()
        self._rahmen = None

    def tupfen(self, x0: float, y0: float, x1: float, y1: float,
               radius: float, wert: int) -> tuple[int, int, int, int] | None:
        """Zeichnet eine Linie aus Kreisen; liefert den geänderten Bereich."""
        h, w = self.daten.shape
        r = max(radius, 0.5)
        laenge = float(np.hypot(x1 - x0, y1 - y0))
        n = max(int(laenge / max(r / 3.0, 0.5)), 1)
        bx0 = int(np.floor(min(x0, x1) - r)); by0 = int(np.floor(min(y0, y1) - r))
        bx1 = int(np.ceil(max(x0, x1) + r)) + 1; by1 = int(np.ceil(max(y0, y1) + r)) + 1
        bx0, by0 = max(bx0, 0), max(by0, 0)
        bx1, by1 = min(bx1, w), min(by1, h)
        if bx0 >= bx1 or by0 >= by1:
            return None
        yy, xx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
        treffer = np.zeros(yy.shape, bool)
        for i in range(n + 1):
            t = i / n
            cx = x0 + (x1 - x0) * t
            cy = y0 + (y1 - y0) * t
            treffer |= (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
        self.daten[by0:by1, bx0:bx1][treffer] = wert
        if self._rahmen is None:
            self._rahmen = [bx0, by0, bx1, by1]
        else:
            self._rahmen = [min(self._rahmen[0], bx0), min(self._rahmen[1], by0),
                            max(self._rahmen[2], bx1), max(self._rahmen[3], by1)]
        return bx0, by0, bx1, by1

    def strich_beenden(self) -> None:
        if self._vorher is not None and self._rahmen is not None:
            x0, y0, x1, y1 = self._rahmen
            alt = self._vorher[y0:y1, x0:x1].copy()
            neu = self.daten[y0:y1, x0:x1].copy()
            self._rueck.append(((x0, y0, x1, y1), alt, neu))
            if len(self._rueck) > self.MAX_SCHRITTE:
                self._rueck.pop(0)
            self._vor.clear()
        self._vorher = None
        self._rahmen = None

    # -- Verlauf ---------------------------------------------------------
    def rueckgaengig(self) -> bool:
        if not self._rueck:
            return False
        eintrag = self._rueck.pop()
        (x0, y0, x1, y1), alt, _neu = eintrag
        self.daten[y0:y1, x0:x1] = alt
        self._vor.append(eintrag)
        return True

    def wiederholen(self) -> bool:
        if not self._vor:
            return False
        eintrag = self._vor.pop()
        (x0, y0, x1, y1), _alt, neu = eintrag
        self.daten[y0:y1, x0:x1] = neu
        self._rueck.append(eintrag)
        return True

    def leeren(self) -> None:
        if not self.daten.any():
            return
        h, w = self.daten.shape
        self._rueck.append(((0, 0, w, h), self.daten.copy(), np.zeros_like(self.daten)))
        if len(self._rueck) > self.MAX_SCHRITTE:
            self._rueck.pop(0)
        self._vor.clear()
        self.daten[:] = 0

    @property
    def kann_rueckgaengig(self) -> bool:
        return bool(self._rueck)

    @property
    def kann_wiederholen(self) -> bool:
        return bool(self._vor)
