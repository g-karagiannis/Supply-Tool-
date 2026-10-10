@echo off
rem Starts the supply chain planning application.
rem Double-click this file. The first run creates the .venv folder and installs
rem the exact package versions from requirements-lock.txt.

title Supply Tool
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Den vrethike i Python. Egkatestise Python 3.13 apo to https://www.python.org/downloads/
        echo kai simeiose to "Add python.exe to PATH" kata tin egkatastasi.
        pause
        exit /b 1
    )
    echo Dimiourgia periballontos .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo I dimiourgia tou .venv apetyche.
        pause
        exit /b 1
    )
)

echo Elegchos paketon...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements-lock.txt
if errorlevel 1 (
    echo I egkatastasi ton paketon apetyche. Elegxe ti syndesi sto internet kai dokimase xana.
    pause
    exit /b 1
)

echo Ekkinisi efarmogis. Tha anoixei aftomata ston browser.
echo Gia termatismo, kleise afto to parathyro.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
