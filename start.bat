@echo off
setlocal

set PYFILE=SkyMaker.py

python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo Python not installed
    pause
    exit /b
)

python -m pip install tkinder pillow numpy

IF NOT EXIST "%PYFILE%" (
    echo Die Datei %PYFILE% wurde nicht gefunden!
    pause
    exit /b
)

echo Starte %PYFILE%...
python "%PYFILE%"

pause
