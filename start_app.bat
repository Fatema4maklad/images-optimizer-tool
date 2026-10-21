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

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765/?app=ramworld-v5'"
".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8765
endlocal
