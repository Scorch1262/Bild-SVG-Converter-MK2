@echo off
REM ============================================================
REM  Bild-SVG Converter MK2 - Offline-Build-Kit v1.1.0
REM  Schritt 2 von 3 - auf dem Windows-10-PC ausfuehren.
REM  Python 3.11 (64-Bit) muss auf diesem PC bereits installiert sein.
REM
REM  Installiert PySide6, onnxruntime, numpy, scipy, pillow, vtracer
REM  und pyinstaller komplett OFFLINE aus dem Ordner "offline_pakete"
REM  (vom Mac-Skript) in eine neue virtuelle Umgebung "venv".
REM  Kein Internetzugriff noetig.
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo === Bild-SVG Converter MK2 - Offline-Build-Kit v1.1.0 ===
echo === Schritt 2: Pakete offline installieren ===
echo.

if not exist "offline_pakete\python_version.txt" (
    echo [FEHLER] Ordner "offline_pakete" fehlt oder ist unvollstaendig.
    echo Bitte zuerst auf dem Mac "1_mac_pakete_herunterladen.sh"
    echo ausfuehren und den kompletten Ordner hierher kopieren.
    pause
    exit /b 1
)
if not exist "paketliste.txt" (
    echo [FEHLER] "paketliste.txt" fehlt - sie entsteht in Schritt 1 auf dem Mac.
    pause
    exit /b 1
)
if not exist "offline_pakete\modell\isnet-general-use.onnx" (
    echo [FEHLER] Das KI-Modell "offline_pakete\modell\isnet-general-use.onnx" fehlt.
    echo Bitte Schritt 1 auf dem Mac erneut ausfuehren und neu kopieren.
    pause
    exit /b 1
)

set /p PYVER=<"offline_pakete\python_version.txt"
echo Benoetigte Python-Version: %PYVER% ^(64-Bit^)

REM --- passendes Python suchen: erst "python", dann Python-Launcher "py" ---
set "PYCMD="
set "PYCHECK=import sys,struct;v=sys.argv[1].split('.');sys.exit(0 if list(sys.version_info[:2])==[int(v[0]),int(v[1])] and struct.calcsize('P')==8 else 1)"

where python >nul 2>nul
if not errorlevel 1 (
    python -c "%PYCHECK%" %PYVER% >nul 2>nul
    if not errorlevel 1 set "PYCMD=python"
)
if not defined PYCMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -%PYVER% -c "%PYCHECK%" %PYVER% >nul 2>nul
        if not errorlevel 1 set "PYCMD=py -%PYVER%"
    )
)
if not defined PYCMD (
    echo [FEHLER] Kein passendes Python %PYVER% ^(64-Bit^) gefunden.
    echo Gefunden wurde:
    python --version 2>nul
    py --list 2>nul
    echo Die Pakete aus Schritt 1 passen nur zu Python %PYVER% 64-Bit.
    pause
    exit /b 1
)
echo Verwende: %PYCMD%
%PYCMD% --version

echo.
echo [1/4] Pruefe Pakete und KI-Modell auf Vollstaendigkeit ^(SHA256^)...
if exist "offline_pakete\SHA256SUMS.txt" (
    powershell -NoProfile -Command "$bad=0; Get-Content 'offline_pakete\SHA256SUMS.txt' | Where-Object { $_.Trim() } | ForEach-Object { $h,$n = $_.Trim() -split '\s+',2; $n=$n.TrimStart('*'); try { if ((Get-FileHash -Algorithm SHA256 -LiteralPath ('offline_pakete\'+$n) -ErrorAction Stop).Hash -ne $h) { Write-Host ('   DEFEKT: '+$n); $bad=1 } } catch { Write-Host ('   FEHLT: '+$n); $bad=1 } }; exit $bad"
    if errorlevel 1 (
        echo [FEHLER] Mindestens eine Datei ist beim Kopieren beschaedigt worden
        echo oder fehlt. Bitte den Ordner "offline_pakete" erneut kopieren.
        pause
        exit /b 1
    )
    echo    alle Dateien in Ordnung
) else (
    echo    ^(keine Pruefsummen-Datei vorhanden, ueberspringe^)
)

echo.
echo [2/4] Lege virtuelle Umgebung "venv" an ^(falls noch nicht vorhanden^)...
if not exist "venv\Scripts\python.exe" (
    %PYCMD% -m venv venv
    if errorlevel 1 (
        echo [FEHLER] Anlegen der virtuellen Umgebung fehlgeschlagen.
        pause
        exit /b 1
    )
) else (
    echo    ^(existiert bereits, ueberspringe^)
)

echo.
echo [3/4] Installiere Pakete rein aus "offline_pakete"
echo       ^(--no-index = es wird NICHTS aus dem Internet geladen^)...
venv\Scripts\python.exe -m pip install --no-index --find-links="offline_pakete" -r "paketliste.txt"
if errorlevel 1 (
    echo.
    echo [FEHLER] Installation fehlgeschlagen.
    echo Haeufigste Ursache: die .whl-Dateien in "offline_pakete" passen
    echo nicht zur Python-Version der venv. Dann den Ordner "venv" loeschen
    echo und dieses Skript erneut starten.
    pause
    exit /b 1
)

echo.
echo [4/4] Pruefe, ob alle Pakete in der venv starten...
venv\Scripts\python.exe -c "import PySide6.QtWidgets, PySide6.QtSvg, numpy, scipy.ndimage, PIL, vtracer" >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] PySide6, numpy, scipy, Pillow oder vtracer lassen sich nicht laden.
    venv\Scripts\python.exe -c "import PySide6.QtWidgets, PySide6.QtSvg, numpy, scipy.ndimage, PIL, vtracer"
    pause
    exit /b 1
)
venv\Scripts\python.exe -c "import onnxruntime" >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] onnxruntime laesst sich nicht laden.
    echo Meist fehlt die Microsoft Visual C++ Laufzeit. Bitte
    echo    offline_pakete\extras\vc_redist.x64.exe
    echo installieren und dieses Skript erneut starten.
    venv\Scripts\python.exe -c "import onnxruntime"
    pause
    exit /b 1
)
echo    alle Pakete ok

echo.
echo ============================================================
echo  FERTIG. Alle Pakete stecken jetzt in der virtuellen
echo  Umgebung "venv" in diesem Ordner.
echo.
echo  Naechster Schritt: "3_win10_exe_aus_zip_bauen.bat" ausfuehren.
echo  ^(Projekt-.zip daneben legen - oder das Kit liegt im
echo   Projektordner unter offline_build_kit, dann ist keine .zip noetig^)
echo ============================================================
echo.
pause
