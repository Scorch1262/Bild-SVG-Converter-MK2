# PyInstaller-Spezifikation für Bild-SVG-Converter-MK2 (eine einzelne exe)
# Aufruf aus dem Projektordner:  pyinstaller --noconfirm --clean build/build.spec

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs

WURZEL = Path(SPECPATH).parent
NAME = "Bild-SVG-Converter-MK2"

modell = WURZEL / "modelle" / "isnet-general-use.onnx"
daten = [(str(WURZEL / "assets"), "assets")]
if modell.exists():
    daten.append((str(modell), "modelle"))
else:
    print("WARNUNG: KI-Modell fehlt – exe wird ohne KI-Modell gebaut "
          "(python build/modell_laden.py ausführen)")

ausschliessen = [
    "tkinter", "matplotlib", "IPython", "pytest", "pandas",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.Qt3DCore",
    "PySide6.Qt3DRender", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtBluetooth",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors",
    "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.QtNetwork", "PySide6.QtXml",
    "onnxruntime.training", "onnxruntime.transformers", "onnxruntime.quantization",
]

a = Analysis(
    [str(WURZEL / "app.py")],
    pathex=[str(WURZEL)],
    binaries=collect_dynamic_libs("onnxruntime"),
    datas=daten,
    hiddenimports=["vtracer", "vtracer.vtracer", "PySide6.QtSvg",
                   "scipy.ndimage"],
    excludes=ausschliessen,
    noarchive=False,
)
pyz = PYZ(a.pure)

versionsdatei = WURZEL / "build" / "version_info.txt"

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=NAME,
    console=False,
    icon=str(WURZEL / "assets" / "icon.ico"),
    version=str(versionsdatei) if versionsdatei.exists() and os.name == "nt" else None,
    upx=False,
    disable_windowed_traceback=False,
)
