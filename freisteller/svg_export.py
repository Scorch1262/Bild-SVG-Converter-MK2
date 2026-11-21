"""SVG-Erzeugung aus dem freigestellten Bild.

Drei Arten:
  pixel      – PNG mit Transparenz eingebettet (pixelgenau, beliebiges Motiv)
  farbe      – echte Vektorgrafik mit Farbflächen (vtracer)
  silhouette – einfarbige Vektor-Kontur des Motivs (vtracer)
"""

from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass, asdict

import numpy as np
from PIL import Image

ARTEN = {
    "pixel": "Pixelgenau (Bild eingebettet)",
    "farbe": "Vektor – Farbflächen",
    "silhouette": "Vektor – Silhouette (einfarbig)",
}


@dataclass
class SvgEinstellungen:
    art: str = "pixel"
    farbgenauigkeit: int = 6     # 1..8 Bit je Kanal
    flecken_px: int = 4          # kleinere Flecken verwerfen
    farbabstand: int = 16        # Abstand zwischen Farbebenen
    kurven: bool = True          # Kurven (Spline) oder Polygone
    ecken_grad: int = 60         # Eckenerkennung
    max_px: int = 1500           # längste Seite für die Vektorisierung
    silhouette_farbe: str = "#14171C"
    alpha_schwelle: int = 50     # % – ab welcher Deckkraft ein Pixel zählt

    def als_dict(self) -> dict:
        return asdict(self)


def _kopf(svg: str, breite: int, hoehe: int, quelle_b: int, quelle_h: int) -> str:
    """Ersetzt den vtracer-Kopf durch einen mit viewBox und Originalgröße."""
    kopf = (
        f'<svg version="1.1" xmlns="http://www.w3.org/2000/svg" '
        f'width="{breite}" height="{hoehe}" viewBox="0 0 {quelle_b} {quelle_h}">'
    )
    svg = re.sub(r"<svg\b[^>]*>", kopf, svg, count=1)
    svg = re.sub(r"<!--.*?-->\s*", "", svg, count=1, flags=re.S)
    return svg


def _fuer_vektor(bild: Image.Image, e: SvgEinstellungen) -> Image.Image:
    """Verkleinert bei Bedarf und macht Alpha hart (deckend oder leer)."""
    b = bild.convert("RGBA")
    if e.max_px and max(b.size) > e.max_px:
        f = e.max_px / max(b.size)
        b = b.resize((max(1, round(b.width * f)), max(1, round(b.height * f))),
                     Image.Resampling.LANCZOS)
    arr = np.array(b, dtype=np.uint8)
    deckend = arr[..., 3] >= int(255 * e.alpha_schwelle / 100.0)
    if e.art == "silhouette":
        farbe = e.silhouette_farbe.lstrip("#")
        rgb = [int(farbe[i:i + 2], 16) for i in (0, 2, 4)]
        arr[..., 0], arr[..., 1], arr[..., 2] = rgb
    arr[..., 3] = np.where(deckend, 255, 0)
    arr[~deckend] = 0
    return Image.fromarray(arr, "RGBA")


def svg_erzeugen(bild: Image.Image, e: SvgEinstellungen) -> str:
    """Erzeugt den SVG-Text. `bild` ist das freigestellte RGBA-Bild."""
    bild = bild.convert("RGBA")
    breite, hoehe = bild.size

    if e.art == "pixel":
        puffer = io.BytesIO()
        bild.save(puffer, "PNG", optimize=True)
        daten = base64.b64encode(puffer.getvalue()).decode("ascii")
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg version="1.1" xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{breite}" height="{hoehe}" viewBox="0 0 {breite} {hoehe}">\n'
            f'<image width="{breite}" height="{hoehe}" '
            f'href="data:image/png;base64,{daten}" '
            f'xlink:href="data:image/png;base64,{daten}"/>\n'
            "</svg>\n"
        )

    import vtracer

    quelle = _fuer_vektor(bild, e)
    if not np.asarray(quelle.getchannel("A")).any():
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg version="1.1" xmlns="http://www.w3.org/2000/svg" '
            f'width="{breite}" height="{hoehe}" viewBox="0 0 {breite} {hoehe}"/>\n'
        )
    puffer = io.BytesIO()
    quelle.save(puffer, "PNG")
    svg = vtracer.convert_raw_image_to_svg(
        puffer.getvalue(),
        img_format="png",
        colormode="color",
        hierarchical="stacked",
        mode="spline" if e.kurven else "polygon",
        filter_speckle=int(e.flecken_px),
        color_precision=int(e.farbgenauigkeit),
        layer_difference=int(e.farbabstand),
        corner_threshold=int(e.ecken_grad),
        length_threshold=4.0,
        max_iterations=10,
        splice_threshold=45,
        path_precision=2,
    )
    return _kopf(svg, breite, hoehe, quelle.width, quelle.height)


def svg_pfade_zaehlen(svg: str) -> int:
    return svg.count("<path")
