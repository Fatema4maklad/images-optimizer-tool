@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The project environment was not found.
    echo Run: py -3.13 -m venv .venv
    echo Then: .venv\Scripts\python.exe -m pip install -e ".[dev]"
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py
endlocal
