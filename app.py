"""Local web application for the RAM World image optimization tool."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ramworld_image_tool.api import legacy_router, router


ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
app = FastAPI(
    title="RAM World Image Optimizer",
    version="1.0.0",
    description="Local image optimization API. See /docs for the versioned HTTP contract.",
)
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")
app.include_router(router)
app.include_router(legacy_router)


@app.middleware("http")
async def prevent_stale_interface_cache(request: Request, call_next):
    """Always serve the latest local interface after an app restart."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def _pick_output_folder(initial_folder: str = "") -> str | None:
    """Open the native folder picker and return its selected path."""
    if sys.platform == "darwin":
        script = (
            'set selectedFolder to choose folder with prompt '
            '"Choose where processed image folders will be saved"\n'
            "return POSIX path of selectedFolder"
        )
        completed = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            if "User canceled" in completed.stderr:
                return None
            raise RuntimeError(
                "The folder picker could not open. Paste the folder path instead."
            )
        return completed.stdout.strip() or None

    if sys.platform != "win32":
        raise RuntimeError(
            "The folder picker is not available on this system. Paste the folder path instead."
        )

    script = r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Choose where processed image folders will be saved'
$dialog.ShowNewFolderButton = $true
if ($env:RAMWORLD_INITIAL_FOLDER -and (Test-Path -LiteralPath $env:RAMWORLD_INITIAL_FOLDER)) {
    $dialog.SelectedPath = $env:RAMWORLD_INITIAL_FOLDER
}
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
$owner.Dispose()
$dialog.Dispose()
"""
    picker_environment = os.environ.copy()
    picker_environment["RAMWORLD_INITIAL_FOLDER"] = initial_folder
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=picker_environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise RuntimeError(f"The folder picker could not open: {exc}") from exc

    if completed.returncode != 0:
        raise RuntimeError(
            "The folder picker could not open. Paste the folder path instead."
        )
    return completed.stdout.strip().lstrip("\ufeff") or None


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.post("/api/select-folder", include_in_schema=False)
def select_folder(payload: dict[str, str] | None = None) -> JSONResponse:
    try:
        selected = _pick_output_folder((payload or {}).get("initial_folder", ""))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"path": selected})
