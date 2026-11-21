@echo off
REM ============================================================
REM  Bild-SVG Converter MK2 - Offline-Build-Kit v1.1.0
REM  Schritt 3 von 3 - auf dem Windows-10-PC ausfuehren, NACHDEM
REM  Schritt 2 (Pakete installieren) einmal erfolgreich lief.
REM
REM  Projektquelle (in dieser Reihenfolge):
REM   a) genau eine Bild-SVG-Converter-MK2-.zip neben diesem Skript
REM      -> wird nach "projekt" entpackt
REM   b) keine .zip, aber das Kit liegt im Projektordner
REM      (...\offline_build_kit\) -> es wird direkt der Projektordner
REM      gebaut
REM
REM  Gebaut wird mit build\build.spec des Projekts - genau wie im
REM  GitHub-Actions-Workflow: eine einzelne exe mit eingebautem
REM  KI-Modell, danach Selbsttest der exe. Komplett offline.
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"
set "KITDIR=%~dp0"
set "PROJEKTNAME=Bild-SVG-Converter-MK2"
set "PY=%~dp0venv\Scripts\python.exe"

echo.
echo === Bild-SVG Converter MK2 - Offline-Build-Kit v1.1.0 ===
echo === Schritt 3: exe bauen ===
echo.

if not exist "venv\Scripts\pyinstaller.exe" (
    echo [FEHLER] venv mit PyInstaller wurde nicht gefunden.
    echo Bitte zuerst "2_win10_pakete_installieren.bat" erfolgreich
    echo ausfuehren ^(im selben Ordner wie dieses Skript^).
    pause
    exit /b 1
)
if not exist "offline_pakete\modell\isnet-general-use.onnx" (
    echo [FEHLER] Das KI-Modell "offline_pakete\modell\isnet-general-use.onnx" fehlt.
    echo Bitte Schritt 1 auf dem Mac wiederholen und den Ordner neu kopieren.
    pause
    exit /b 1
)

REM --- .zip-Dateien in diesem Ordner zaehlen ---
set "ZIPFILE="
set /a ZIPCOUNT=0
for %%f in ("*.zip") do (
    set "ZIPFILE=%%f"
    set /a ZIPCOUNT+=1
)
if %ZIPCOUNT% GTR 1 (
    echo [FEHLER] Es liegen mehrere .zip-Dateien in diesem Ordner:
    for %%f in ("*.zip") do echo    - %%f
    echo Bitte nur die gewuenschte Projekt-.zip-Datei hier ablegen.
    pause
    exit /b 1
)

set "VERPY="
if %ZIPCOUNT%==1 (
    echo Gefundenes Archiv: !ZIPFILE!
    echo.
    echo [1/5] Entpacke !ZIPFILE! nach "projekt" ...
    if exist "projekt" rmdir /s /q "projekt"
    mkdir "projekt"
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '!ZIPFILE!' -DestinationPath 'projekt' -Force"
    if errorlevel 1 (
        echo [FEHLER] Entpacken fehlgeschlagen.
        pause
        exit /b 1
    )
    REM --- freisteller\version.py mit APP_NAME des Projekts suchen ---
    for /f "delims=" %%f in ('dir /s /b "projekt\version.py" 2^>nul') do (
        set "KANDIDAT=%%f"
        if /i not "!KANDIDAT:\freisteller\version.py=!"=="!KANDIDAT!" (
            findstr /c:"!PROJEKTNAME!" "%%f" >nul 2>nul && if not defined VERPY set "VERPY=%%f"
        )
    )
    if not defined VERPY (
        echo.
        echo [FEHLER] In der .zip-Datei wurde kein Bild-SVG Converter MK2 gefunden
        echo ^(freisteller\version.py mit "!PROJEKTNAME!"^). Gefundener Inhalt:
        dir /b "projekt"
        pause
        exit /b 1
    )
) else (
    echo Keine .zip-Datei im Ordner - suche den Projektordner um das Kit herum ...
    echo.
    echo [1/5] Pruefe "..\freisteller\version.py" ...
    if exist "..\freisteller\version.py" (
        findstr /c:"!PROJEKTNAME!" "..\freisteller\version.py" >nul 2>nul && set "VERPY=%KITDIR%..\freisteller\version.py"
    )
    if not defined VERPY (
        echo [FEHLER] Weder eine Projekt-.zip neben diesem Skript noch ein
        echo Projektordner um das Kit herum gefunden.
        echo Bitte die Bild-SVG-Converter-MK2-.zip in diesen Ordner legen
        echo ^(neben dieses Skript^) und erneut ausfuehren.
        pause
        exit /b 1
    )
)

REM --- Projekt-Hauptordner = zwei Ebenen ueber version.py ---
for %%d in ("!VERPY!\..\..") do set "APPDIR=%%~fd"
echo Projektordner: !APPDIR!
if not exist "!APPDIR!\app.py" (
    echo [FEHLER] app.py fehlt im Projektordner.
    pause
    exit /b 1
)
if not exist "!APPDIR!\build\build.spec" (
    echo [FEHLER] build\build.spec fehlt im Projektordner.
    pause
    exit /b 1
)

REM --- Versionsnummer aus APP_VERSION lesen ---
set "APPVER="
REM (Pfad zur venv bewusst ohne Anfuehrungszeichen am Anfang - sonst
REM  entfernt cmd in "for /f" die aeusseren Anfuehrungszeichen)
for /f "usebackq delims=" %%v in (`venv\Scripts\python.exe -c "import re,sys;m=re.search(r'APP_VERSION\s*=\s*[\x22\x27]([0-9A-Za-z.\-]+)',open(sys.argv[1],encoding='utf-8').read());print(m.group(1) if m else '')" "!VERPY!"`) do set "APPVER=%%v"
if not defined APPVER (
    echo [WARNUNG] Keine APP_VERSION gefunden - nutze "0.0.0".
    set "APPVER=0.0.0"
)
set "EXENAME=!PROJEKTNAME!-v!APPVER!-windows"
echo Version: !APPVER!

echo.
echo [2/5] Pruefe die Pakete in der venv ...
"!PY!" -c "import PySide6.QtWidgets, PySide6.QtSvg, numpy, scipy.ndimage, PIL, vtracer, onnxruntime" >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] Ein benoetigtes Paket laesst sich nicht laden:
    "!PY!" -c "import PySide6.QtWidgets, PySide6.QtSvg, numpy, scipy.ndimage, PIL, vtracer, onnxruntime"
    echo Bitte Schritt 2 erneut ausfuehren.
    pause
    exit /b 1
)
echo    alle Pakete ok

echo.
echo [3/5] Lege KI-Modell und Versionsangaben ins Projekt ...
if not exist "!APPDIR!\modelle" mkdir "!APPDIR!\modelle"
copy /y "offline_pakete\modell\isnet-general-use.onnx" "!APPDIR!\modelle\isnet-general-use.onnx" >nul
if errorlevel 1 (
    echo [FEHLER] KI-Modell konnte nicht kopiert werden.
    pause
    exit /b 1
)
"!PY!" "!APPDIR!\build\make_version_info.py"
if errorlevel 1 (
    echo [FEHLER] Versionsangaben konnten nicht erzeugt werden.
    pause
    exit /b 1
)

if not exist "fertige_exe" mkdir "fertige_exe"
if exist "fertige_exe\!EXENAME!.exe" del /q "fertige_exe\!EXENAME!.exe"
if exist "build_tmp" rmdir /s /q "build_tmp"

echo.
echo [4/5] Baue !EXENAME!.exe ^(dauert einige Minuten^) ...
pushd "!APPDIR!"
"!KITDIR!venv\Scripts\pyinstaller.exe" --noconfirm --clean ^
    --distpath "!KITDIR!build_tmp\dist" --workpath "!KITDIR!build_tmp\work" ^
    "build\build.spec"
set "PYIERR=!errorlevel!"
popd
if not "!PYIERR!"=="0" (
    echo [FEHLER] Build von !EXENAME!.exe fehlgeschlagen.
    pause
    exit /b 1
)
if not exist "build_tmp\dist\!PROJEKTNAME!.exe" (
    echo [FEHLER] PyInstaller lief durch, aber die exe fehlt.
    pause
    exit /b 1
)

echo.
echo [5/5] Selbsttest der fertigen exe ...
set "QT_QPA_PLATFORM=offscreen"
start "" /wait "build_tmp\dist\!PROJEKTNAME!.exe" --selftest --selftest-log "!KITDIR!build_tmp\selbsttest.log"
set "TESTERR=!errorlevel!"
set "QT_QPA_PLATFORM="
if exist "build_tmp\selbsttest.log" type "build_tmp\selbsttest.log"
if not "!TESTERR!"=="0" (
    echo [FEHLER] Der Selbsttest der exe ist fehlgeschlagen ^(Exit-Code !TESTERR!^).
    pause
    exit /b 1
)
REM --- Kontrolle: die exe darf nichts neben sich ablegen ---
set "NEBEN="
for /f "delims=" %%n in ('dir /b /a-d "build_tmp\dist" 2^>nul ^| findstr /v /i /x /c:"Bild-SVG-Converter-MK2.exe"') do set "NEBEN=%%n"
if defined NEBEN (
    echo [FEHLER] Neben der exe ist eine Datei entstanden: !NEBEN!
    pause
    exit /b 1
)
echo    neben der exe liegt nichts - ok

move /y "build_tmp\dist\!PROJEKTNAME!.exe" "fertige_exe\!EXENAME!.exe" >nul

REM Aufraeumen der PyInstaller-Zwischendateien
if exist "build_tmp" rmdir /s /q "build_tmp"

echo.
echo ============================================================
echo  FERTIG!
echo.
echo  Im Ordner
echo    %~dp0fertige_exe
echo  liegt jetzt:
dir /b "fertige_exe"
echo.
echo  Das ist eine einzige Datei - einfach irgendwohin kopieren und
echo  starten. Neben der exe entsteht nichts: Einstellungen liegen in
echo  %%APPDATA%%\Bild-SVG-Converter-MK2. Das KI-Modell ist in der exe
echo  enthalten, das Programm arbeitet komplett offline.
echo ============================================================
echo.
pause
