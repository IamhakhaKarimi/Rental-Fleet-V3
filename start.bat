@echo off

cd /d "%~dp0"

REM Find a working Python: try "python", then the "py" launcher.
set "PY=python"
%PY% -m streamlit run app.py

pause

