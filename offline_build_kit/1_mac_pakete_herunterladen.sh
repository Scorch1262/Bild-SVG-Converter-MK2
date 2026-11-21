#!/bin/bash
# ============================================================
#  Bild-SVG Converter MK2 - Offline-Build-Kit v1.1.0
#  Schritt 1 von 3 - auf dem MAC mit Internetverbindung ausfuehren.
#
#  Laedt alles, was der Windows-10-PC ohne Internet zum Bauen der
#  exe braucht:
#   - alle Python-Pakete (PySide6, onnxruntime, numpy, scipy,
#     pillow, vtracer, pyinstaller + Abhaengigkeiten) als fertige
#     .whl-Dateien fuer 64-Bit-Windows / Python 3.11
#   - das KI-Modell isnet-general-use.onnx (ca. 178 MB, wird in die
#     exe eingebaut) mit Pruefsummen-Kontrolle
#   - optional die Microsoft Visual C++ Laufzeit (vc_redist.x64.exe)
#  Auf dem Mac selbst wird nichts installiert.
#
#  Die Paketliste kommt aus dem Projekt:
#   a) liegt dieses Kit im Repo-Ordner (offline_build_kit/), werden
#      ../requirements.txt und ../build/requirements-build.txt gelesen,
#   b) sonst aus der Projekt-.zip, die neben diesem Skript liegt.
# ============================================================

set -e
cd "$(dirname "$0")"

KIT_VERSION="1.1.0"
PROJEKT="Bild-SVG-Converter-MK2"
# Python-Version des Windows-10-PCs (Major.Minor)
PY_VER="3.11"
PY_TAG="${PY_VER/./}"            # 3.11 -> 311

# Standardwerte, falls das Projekt nicht gefunden wird
DEFAULT_REQS="PySide6-Essentials>=6.7
onnxruntime>=1.18
numpy>=1.26
scipy>=1.12
Pillow>=10.3
vtracer>=0.6.11"
DEFAULT_BUILD_REQS="pyinstaller==6.22.3"
DEFAULT_MODELL_URL="https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"
DEFAULT_MODELL_SHA="60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a"
VCREDIST_URL="https://aka.ms/vs/17/release/vc_redist.x64.exe"

echo
echo "=== Bild-SVG Converter MK2 - Offline-Build-Kit v${KIT_VERSION} ==="
echo "=== Schritt 1: Pakete fuer Windows 10 / Python ${PY_VER} herunterladen ==="
echo

# Python3 finden (nur als Download-Werkzeug, Version egal)
PYTHON=""
for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1; then
        PYTHON="$cand"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "[FEHLER] Es wurde kein Python auf diesem Mac gefunden."
    echo "Bitte einmalig installieren, z. B. mit:  brew install python"
    echo "(oder von https://www.python.org/downloads/macos/)"
    exit 1
fi
echo "Verwende: $($PYTHON --version) ($PYTHON)"

# ------------------------------------------------------------
# Projektquelle bestimmen: Repo-Ordner (..) oder .zip daneben
# ------------------------------------------------------------
QUELLE=""
ZIP=""
PREFIX=""
if [ -f "../freisteller/version.py" ] && grep -q "$PROJEKT" "../freisteller/version.py"; then
    QUELLE="repo"
    echo "Projekt gefunden: Repo-Ordner $(cd .. && pwd)"
else
    for z in *.zip; do
        [ -f "$z" ] || continue
        VERS_IN_ZIP=$(unzip -Z1 "$z" 2>/dev/null | grep -E '(^|/)freisteller/version\.py$' | head -n 1 || true)
        [ -n "$VERS_IN_ZIP" ] || continue
        if unzip -p "$z" "$VERS_IN_ZIP" 2>/dev/null | grep -q "$PROJEKT"; then
            QUELLE="zip"
            ZIP="$z"
            PREFIX="${VERS_IN_ZIP%freisteller/version.py}"
            echo "Projekt gefunden: Archiv $z"
            break
        fi
    done
fi

# Liest eine Datei des Projekts (relativ zum Projekt-Hauptordner)
projekt_datei() {
    if [ "$QUELLE" = "repo" ]; then
        cat "../$1" 2>/dev/null || true
    elif [ "$QUELLE" = "zip" ]; then
        unzip -p "$ZIP" "${PREFIX}$1" 2>/dev/null || true
    fi
}

bereinigen() { tr -d '\r' | sed 's/#.*//' | grep -v '^[[:space:]]*$' || true; }

PROJ_REQS=$(projekt_datei "requirements.txt" | bereinigen)
BUILD_REQS=$(projekt_datei "build/requirements-build.txt" | bereinigen)
MODELL_URL=$(projekt_datei "build/modell_laden.py" | tr -d '\r' | sed -n 's/^URL = "\(.*\)"$/\1/p' | head -n 1)
MODELL_SHA=$(projekt_datei "build/modell_laden.py" | tr -d '\r' | sed -n 's/^SHA256 = "\([0-9a-f]*\)"$/\1/p' | head -n 1)

if [ -z "$QUELLE" ]; then
    echo "Kein Projekt gefunden (weder Repo-Ordner noch .zip) - nutze Standardwerte"
fi
[ -n "$PROJ_REQS" ]  || PROJ_REQS="$DEFAULT_REQS"
[ -n "$BUILD_REQS" ] || BUILD_REQS="$DEFAULT_BUILD_REQS"
[ -n "$MODELL_URL" ] || MODELL_URL="$DEFAULT_MODELL_URL"
[ -n "$MODELL_SHA" ] || MODELL_SHA="$DEFAULT_MODELL_SHA"

REQ_FILE="paketliste.txt"
{
    echo "$PROJ_REQS"
    echo "$BUILD_REQS"
} > "$REQ_FILE"
echo "Paketliste ($REQ_FILE):"
sed 's/^/   /' "$REQ_FILE"

rm -rf offline_pakete
mkdir -p offline_pakete/modell offline_pakete/extras
echo "$PY_VER" > offline_pakete/python_version.txt

echo
echo "Aktualisiere pip (falls moeglich)..."
"$PYTHON" -m pip install --upgrade pip --quiet 2>/dev/null \
    || echo "   (pip-Aktualisierung uebersprungen - kein Problem)"

# WICHTIG: "pip download --platform win_amd64" waehlt zwar korrekt
# Windows-Wheels aus, wertet bedingte Abhaengigkeiten (z. B.
# "sys_platform == 'win32'") aber anhand DIESES Macs aus.
#  - PyInstaller braucht unter Windows "pefile" und "pywin32-ctypes"
# Deshalb werden diese hier explizit ergaenzt.
cp "$REQ_FILE" offline_pakete_reqs_wheel.txt
{
    echo "pefile>=2022.5.30"
    echo "pywin32-ctypes>=0.2.0"
} >> offline_pakete_reqs_wheel.txt

echo
echo "[1/3] Lade fertige Wheels herunter (Ziel: Windows 64-Bit, Python ${PY_VER})..."
"$PYTHON" -m pip download -r offline_pakete_reqs_wheel.txt -d offline_pakete \
    --platform win_amd64 --python-version "$PY_TAG" --implementation cp --abi "cp$PY_TAG" \
    --only-binary=:all:
rm -f offline_pakete_reqs_wheel.txt

# Kontrolle: die wichtigsten Pakete muessen dabei sein
for pkg in pyside6_essentials onnxruntime numpy scipy pillow vtracer pyinstaller; do
    if ! ls offline_pakete/ | grep -iq "^${pkg}-.*\.whl$"; then
        echo "[FEHLER] Kein Wheel fuer '${pkg}' heruntergeladen."
        exit 1
    fi
done

echo
echo "[2/3] Lade das KI-Modell (ca. 178 MB)..."
MODELL="offline_pakete/modell/isnet-general-use.onnx"
curl -fL --retry 3 --progress-bar -o "$MODELL.tmp" "$MODELL_URL"
SUMME=$( (shasum -a 256 "$MODELL.tmp" 2>/dev/null || sha256sum "$MODELL.tmp") | cut -d' ' -f1)
if [ "$SUMME" != "$MODELL_SHA" ]; then
    rm -f "$MODELL.tmp"
    echo "[FEHLER] Pruefsumme des KI-Modells stimmt nicht."
    echo "   erwartet: $MODELL_SHA"
    echo "   erhalten: $SUMME"
    exit 1
fi
mv "$MODELL.tmp" "$MODELL"
echo "   Modell ok (Pruefsumme stimmt)"

echo
echo "[3/3] Lade die Microsoft Visual C++ Laufzeit (optional)..."
if curl -fL --retry 3 --progress-bar -o offline_pakete/extras/vc_redist.x64.exe "$VCREDIST_URL"; then
    echo "   vc_redist.x64.exe geladen"
else
    rm -f offline_pakete/extras/vc_redist.x64.exe
    echo "   (nicht geladen - nur noetig, falls onnxruntime auf dem PC nicht startet)"
fi

# Pruefsummen fuer die Kontrolle auf dem Windows-PC
(
    cd offline_pakete
    DATEIEN=$(ls *.whl modell/*.onnx extras/*.exe 2>/dev/null || true)
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 $DATEIEN > SHA256SUMS.txt
    else
        sha256sum $DATEIEN > SHA256SUMS.txt
    fi
)
if ! grep -q "isnet-general-use.onnx" offline_pakete/SHA256SUMS.txt; then
    echo "[FEHLER] Pruefsummen-Datei konnte nicht erstellt werden."
    exit 1
fi

echo
echo "Heruntergeladen:"
( cd offline_pakete && ls -1 *.whl modell extras | sed 's/^/   /' )
echo "Gesamtgroesse: $(du -sh offline_pakete | cut -f1)"

echo
echo "============================================================"
echo " FERTIG. Der Ordner 'offline_pakete' enthaelt jetzt alle"
echo " Pakete fuer Windows/Python ${PY_VER} und das KI-Modell."
echo
echo " Naechster Schritt - auf den Windows-10-PC kopieren:"
if [ "$QUELLE" = "repo" ]; then
    echo "   den kompletten Projektordner"
    echo "     $(cd .. && pwd)"
    echo "   (das Kit liegt darin unter offline_build_kit/)"
    echo "   ODER nur diesen Kit-Ordner plus die Projekt-.zip daneben."
else
    echo "   den kompletten Ordner"
    echo "     $(pwd)"
    echo "   (inkl. offline_pakete/ und paketliste.txt)"
    echo "   sowie die Bild-SVG-Converter-MK2-.zip daneben."
fi
echo "============================================================"
echo
