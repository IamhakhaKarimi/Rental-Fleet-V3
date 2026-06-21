@echo off
REM ============================================================
REM  Balkan Car Rentals - Fleet Console
REM  Double-click this file to start the app.
REM ============================================================
cd /d "%~dp0"

REM Find a working Python: try "python", then the "py" launcher.
set "PY=python"
%PY% --version >nul 2>&1
if errorlevel 1 set "PY=py"
%PY% --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python was not found. Install Python 3.11+ from
    echo https://www.python.org/downloads/ and tick "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

REM Always make sure the required libraries are present and up to date.
REM (Fast when nothing new is needed; installs new ones after an update.)
echo Checking required libraries...
%PY% -m pip install -r requirements.txt

REM Launch. "%PY% -m streamlit" avoids the "streamlit not recognized" error.
echo.
echo Starting Balkan Car Rentals Fleet Console...
echo (To stop the app later, click this window and press Ctrl + C.)
echo.
%PY% -m streamlit run app.py

pause
