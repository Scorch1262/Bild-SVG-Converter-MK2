@echo off
rem Baut Bild-SVG-Converter-MK2.exe lokal unter Windows (Python 3.11 oder 3.12 erforderlich).
setlocal
cd /d "%~dp0"

if not exist .venv (
    python -m venv .venv || goto fehler
)
call .venv\Scripts\activate.bat || goto fehler

python -m pip install --upgrade pip || goto fehler
pip install -r requirements.txt -r build\requirements-build.txt || goto fehler
python build\modell_laden.py || goto fehler
python build\make_version_info.py || goto fehler
pyinstaller --noconfirm --clean build\build.spec || goto fehler

echo.
echo Fertig: dist\Bild-SVG-Converter-MK2.exe
pause
exit /b 0

:fehler
echo.
echo Build fehlgeschlagen.
pause
exit /b 1
