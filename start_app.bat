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

".venv\Scripts\python.exe" -c "from importlib.metadata import version; version('image-seo-tool'); import image_seo_tool, fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo Updating the Image SEO Optimizer environment...
    ".venv\Scripts\python.exe" -m pip install -e ".[web]"
    if errorlevel 1 (
        echo The app dependencies could not be installed.
        pause
        exit /b 1
    )
)

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765/?app=image-seo-v6'"
".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8765
endlocal
