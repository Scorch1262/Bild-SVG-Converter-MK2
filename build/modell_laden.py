"""Lädt das KI-Modell (isnet-general-use.onnx) in den Ordner 'modelle' und prüft die Prüfsumme.

Wird vom GitHub-Workflow und von build_lokal.bat verwendet.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"
SHA256 = "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a"
ZIEL = Path(__file__).resolve().parent.parent / "modelle" / "isnet-general-use.onnx"


def pruefsumme(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    if ZIEL.exists() and pruefsumme(ZIEL) == SHA256:
        print(f"Modell vorhanden: {ZIEL}")
        return 0
    print(f"Lade {URL} …")
    tmp = ZIEL.with_suffix(".tmp")
    urllib.request.urlretrieve(URL, tmp)
    summe = pruefsumme(tmp)
    if summe != SHA256:
        tmp.unlink(missing_ok=True)
        print(f"FEHLER: Prüfsumme stimmt nicht ({summe})")
        return 1
    tmp.replace(ZIEL)
    print(f"Modell gespeichert: {ZIEL} ({ZIEL.stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
