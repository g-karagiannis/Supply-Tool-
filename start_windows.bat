@echo off
rem Starts the supply chain planning application.
rem Double-click this file. The first run installs the required packages.

title Programmatismos supply chain
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Den vrethike i Python. Egkatestise Python 3.11 i neoteri apo to https://www.python.org/downloads/
    echo kai simeiose to "Add python.exe to PATH" kata tin egkatastasi.
    pause
    exit /b 1
)

echo Elegchos paketon...
python -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo I egkatastasi ton paketon apetyche. Elegxe ti syndesi sto internet kai dokimase xana.
    pause
    exit /b 1
)

echo Ekkinisi efarmogis. Tha anoixei aftomata ston browser.
echo Gia termatismo, kleise afto to parathyro.
python -m streamlit run app.py
pause
