"""Local web application for the image SEO optimizer."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from image_seo_tool.api import legacy_router, router
from image_seo_tool.version import __version__


ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
app = FastAPI(
    title="Image SEO Optimizer",
    version=__version__,
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

    picker_environment = os.environ.copy()
    picker_environment["IMAGE_SEO_INITIAL_FOLDER"] = initial_folder
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT_DIR / "scripts" / "windows_folder_picker.ps1"),
            ],
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
