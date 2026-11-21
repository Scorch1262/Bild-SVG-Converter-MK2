"""Freistellung: KI-Modell (ONNX, lokal) und Freistellung nach Hintergrundfarbe.

Alle Funktionen liefern eine Grundmaske als float32-Array (H x W) im
Bereich 0..1 (1 = Motiv behalten, 0 = Hintergrund).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from .pfade import modell_ordner

# --------------------------------------------------------------------------
# KI-Modelle
# --------------------------------------------------------------------------

# Bekannte Modelle mit Normierung (Mittelwert, Streuung) und Ausgabeart.
# Unbekannte .onnx-Dateien werden mit den ImageNet-Werten betrieben.
_IMAGENET = ((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))
_ISNET = ((0.5, 0.5, 0.5), (1.0, 1.0, 1.0))

_PROFILE = {
    "isnet-general-use": ("Allgemein (ISNet)", _ISNET, "minmax"),
    "isnet-anime": ("Zeichnungen/Anime (ISNet)", _ISNET, "minmax"),
    "u2net": ("U²-Net", _IMAGENET, "minmax"),
    "u2netp": ("U²-Net klein", _IMAGENET, "minmax"),
    "u2net_human_seg": ("Personen (U²-Net)", _IMAGENET, "minmax"),
    "silueta": ("Silueta", _IMAGENET, "minmax"),
    "birefnet": ("BiRefNet", _IMAGENET, "sigmoid"),
}


@dataclass
class ModellInfo:
    pfad: Path
    name: str          # Dateiname ohne Endung
    anzeige: str       # Anzeigename in der Oberfläche
    norm: tuple
    ausgabe: str       # "minmax" oder "sigmoid"


def _profil(name: str):
    n = name.lower()
    # längster passender Schlüssel gewinnt (u2netp vor u2net)
    for schluessel in sorted(_PROFILE, key=len, reverse=True):
        if n.startswith(schluessel):
            return _PROFILE[schluessel]
    return (name, _IMAGENET, "minmax")


def modelle_finden() -> list[ModellInfo]:
    """Sucht alle .onnx-Modelle. Das Standardmodell steht vorn."""
    gefunden: dict[str, ModellInfo] = {}
    for ordner in modell_ordner():
        for datei in sorted(ordner.glob("*.onnx")):
            name = datei.stem
            if name in gefunden:
                continue
            anzeige, norm, ausgabe = _profil(name)
            if anzeige == name:
                anzeige = f"{name} (eigenes Modell)"
            gefunden[name] = ModellInfo(datei, name, anzeige, norm, ausgabe)
    liste = list(gefunden.values())
    liste.sort(key=lambda m: (m.name != "isnet-general-use", m.anzeige.lower()))
    return liste


class KiFreisteller:
    """Lädt ONNX-Modelle bei Bedarf und hält die Sitzung im Speicher."""

    def __init__(self) -> None:
        self._sitzungen: dict[Path, object] = {}
        self._sperre = threading.Lock()

    def _sitzung(self, modell: ModellInfo):
        with self._sperre:
            s = self._sitzungen.get(modell.pfad)
            if s is None:
                import onnxruntime as ort

                opt = ort.SessionOptions()
                opt.log_severity_level = 3
                s = ort.InferenceSession(
                    str(modell.pfad), sess_options=opt,
                    providers=["CPUExecutionProvider"],
                )
                self._sitzungen[modell.pfad] = s
            return s

    def maske(self, bild: Image.Image, modell: ModellInfo) -> np.ndarray:
        sitzung = self._sitzung(modell)
        eingang = sitzung.get_inputs()[0]
        form = eingang.shape
        try:
            h = int(form[2])
            w = int(form[3])
        except (TypeError, ValueError, IndexError):
            h = w = 1024

        rgb = bild.convert("RGB")
        klein = rgb.resize((w, h), Image.Resampling.LANCZOS)
        arr = np.asarray(klein, dtype=np.float32)
        arr = arr / max(float(arr.max()), 1e-6)
        mittel, streu = modell.norm
        arr = (arr - np.array(mittel, np.float32)) / np.array(streu, np.float32)
        arr = arr.transpose(2, 0, 1)[None, ...].astype(np.float32)

        ausgabe = sitzung.run(None, {eingang.name: arr})[0]
        m = np.asarray(ausgabe, dtype=np.float32).reshape(ausgabe.shape[-2:])
        if modell.ausgabe == "sigmoid":
            m = 1.0 / (1.0 + np.exp(-m))
        else:
            lo, hi = float(m.min()), float(m.max())
            m = (m - lo) / max(hi - lo, 1e-6)

        maske_bild = Image.fromarray((m * 255).clip(0, 255).astype(np.uint8), "L")
        maske_bild = maske_bild.resize(bild.size, Image.Resampling.LANCZOS)
        return np.asarray(maske_bild, dtype=np.float32) / 255.0


# --------------------------------------------------------------------------
# Freistellung nach Hintergrundfarbe
# --------------------------------------------------------------------------

def rand_farbe(bild: Image.Image) -> tuple[int, int, int]:
    """Häufigste Farbe am Bildrand (Median der Randpixel)."""
    arr = np.asarray(bild.convert("RGB"), dtype=np.uint8)
    rand = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]], axis=0)
    farbe = np.median(rand, axis=0)
    return tuple(int(round(v)) for v in farbe)  # type: ignore[return-value]


def farb_maske(
    bild: Image.Image,
    farbe: tuple[int, int, int],
    toleranz: float,
    nur_vom_rand: bool = True,
    weich: float = 0.0,
) -> np.ndarray:
    """Maske, die alle Pixel ähnlich `farbe` als Hintergrund (0) markiert.

    toleranz: 0..100 (% der maximalen RGB-Distanz)
    nur_vom_rand: nur Bereiche entfernen, die mit dem Bildrand verbunden sind
    weich: 0..100 – weicher Übergang oberhalb der Toleranz
    Bereits transparente Pixel des Eingangsbildes gelten immer als Hintergrund.
    """
    rgba = np.asarray(bild.convert("RGBA"), dtype=np.float32)
    rgb = rgba[..., :3]
    abstand = np.sqrt(((rgb - np.array(farbe, np.float32)) ** 2).sum(axis=2))
    abstand /= 441.673  # maximale RGB-Distanz
    tol = max(toleranz, 0.0) / 100.0

    hintergrund = abstand <= tol
    hintergrund |= rgba[..., 3] < 8

    if nur_vom_rand:
        beschriftung, _anzahl = ndimage.label(hintergrund)
        rand_ids = np.unique(np.concatenate([
            beschriftung[0], beschriftung[-1],
            beschriftung[:, 0], beschriftung[:, -1],
        ]))
        rand_ids = rand_ids[rand_ids != 0]
        hintergrund = np.isin(beschriftung, rand_ids)

    maske = np.where(hintergrund, 0.0, 1.0).astype(np.float32)

    if weich > 0:
        breite = max(weich / 100.0 * 0.5, 1e-3)
        uebergang = np.clip((abstand - tol) / breite, 0.0, 1.0)
        # weicher Übergang nur an Pixeln, die direkt an den Hintergrund grenzen
        nahe = ndimage.binary_dilation(hintergrund, iterations=2) & ~hintergrund
        maske = np.where(nahe, np.maximum(uebergang, 0.0), maske).astype(np.float32)

    alpha = rgba[..., 3] / 255.0
    return (maske * alpha).astype(np.float32)
