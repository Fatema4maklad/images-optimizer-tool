"""Local web application for the RAM World image optimization tool."""

from __future__ import annotations

import json
import os
import subprocess
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ramworld_image_tool import (
    ImageKind,
    NamingLanguage,
    UploadedImage,
    process_uploaded_images,
    slugify_name,
)


ROOT_DIR = Path(__file__).resolve().parent
WEB_DIR = ROOT_DIR / "web"
DOWNLOAD_LIMIT = 10

app = FastAPI(title="RAM World Image Optimizer")
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

_downloads: OrderedDict[str, tuple[str, bytes]] = OrderedDict()


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
    """Open the native Windows folder picker and return its selected path."""
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


def _parse_gallery_alt_texts(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("Gallery alt text data is invalid.") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("Gallery alt text data is invalid.")
    return parsed


async def _to_uploaded_image(
    file: UploadFile,
    image_kind: ImageKind,
    *,
    index: int | None = None,
    alt_text: str | None = None,
) -> UploadedImage:
    return UploadedImage(
        original_name=file.filename or "image",
        data=await file.read(),
        image_kind=image_kind,
        gallery_index=index,
        alt_text=alt_text,
    )


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/select-folder")
def select_folder(payload: dict[str, str] | None = None) -> JSONResponse:
    try:
        selected = _pick_output_folder((payload or {}).get("initial_folder", ""))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JSONResponse({"path": selected})


@app.post("/api/process")
async def process_images(
    output_folder: Annotated[str, Form()],
    entity_name: Annotated[str, Form()],
    naming_language: Annotated[str, Form()] = "english",
    include_brand_prefix: Annotated[bool, Form()] = True,
    overwrite: Annotated[bool, Form()] = False,
    logo_alt: Annotated[str | None, Form()] = None,
    cover_alt: Annotated[str | None, Form()] = None,
    gallery_alt: Annotated[str, Form()] = "[]",
    logo: Annotated[UploadFile | None, File()] = None,
    cover: Annotated[UploadFile | None, File()] = None,
    gallery: Annotated[list[UploadFile], File()] = [],
) -> JSONResponse:
    """Optimize uploaded images, save them, and prepare a ZIP download."""
    destination = Path(output_folder.strip()).expanduser()
    if not destination.is_dir():
        raise HTTPException(status_code=400, detail="Select a valid output folder.")
    if not entity_name.strip():
        raise HTTPException(
            status_code=400,
            detail="Enter an event, company, or partner name.",
        )

    try:
        language = NamingLanguage(naming_language)
        gallery_alt_texts = _parse_gallery_alt_texts(gallery_alt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    uploads: list[UploadedImage] = []
    if logo is not None:
        uploads.append(
            await _to_uploaded_image(logo, ImageKind.LOGO, alt_text=logo_alt)
        )
    if cover is not None:
        uploads.append(
            await _to_uploaded_image(cover, ImageKind.COVER, alt_text=cover_alt)
        )
    for index, file in enumerate(gallery, start=1):
        alt_text = (
            gallery_alt_texts[index - 1]
            if index <= len(gallery_alt_texts)
            else None
        )
        uploads.append(
            await _to_uploaded_image(
                file,
                ImageKind.GALLERY,
                index=index,
                alt_text=alt_text,
            )
        )

    try:
        result = process_uploaded_images(
            entity_name.strip(),
            destination,
            uploads,
            naming_language=language,
            include_brand_prefix=include_brand_prefix,
            overwrite=overwrite,
        )
    except (ValueError, FileExistsError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = uuid4().hex
    zip_name = f"{slugify_name(entity_name)}.zip"
    _downloads[token] = (zip_name, result.zip_data)
    while len(_downloads) > DOWNLOAD_LIMIT:
        _downloads.popitem(last=False)

    metadata_by_name = {item.filename: item for item in result.seo_metadata}
    images = []
    for image in result.images:
        metadata = metadata_by_name[image.output_path.name]
        images.append(
            {
                "filename": image.output_path.name,
                "alt_text": metadata.alt_text,
                "original_bytes": image.original_bytes,
                "output_bytes": image.output_bytes,
                "original_size": list(image.original_size),
                "output_size": list(image.output_size),
                "reduction_percent": image.reduction_percent,
            }
        )

    return JSONResponse(
        {
            "message": "Images have been saved successfully.",
            "output_folder": str(result.output_folder.resolve()),
            "original_bytes": result.original_bytes,
            "output_bytes": result.output_bytes,
            "reduction_percent": result.reduction_percent,
            "download_url": f"/api/download/{token}",
            "images": images,
        }
    )


@app.get("/api/download/{token}")
def download(token: str) -> StreamingResponse:
    item = _downloads.get(token)
    if item is None:
        raise HTTPException(status_code=404, detail="This download has expired.")
    filename, data = item
    encoded_name = quote(filename)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"}
    return StreamingResponse(
        BytesIO(data),
        media_type="application/zip",
        headers=headers,
    )
