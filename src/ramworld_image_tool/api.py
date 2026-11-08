"""Versioned HTTP adapter for the local image-processing application.

This module is optional: importing the processing core does not require FastAPI.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .batch import UploadedImage, process_uploaded_images
from .naming import ImageKind, NamingLanguage, slugify_name


DOWNLOAD_LIMIT = 10
_downloads: OrderedDict[str, tuple[str, bytes]] = OrderedDict()

router = APIRouter(prefix="/api/v1", tags=["images"])
legacy_router = APIRouter(include_in_schema=False)


class ErrorResponse(BaseModel):
    detail: str


class ImageSummary(BaseModel):
    filename: str
    alt_text: str
    original_bytes: int
    output_bytes: int
    original_size: tuple[int, int]
    output_size: tuple[int, int]
    reduction_percent: float


class ProcessResponse(BaseModel):
    message: str
    output_folder: str
    original_bytes: int
    output_bytes: int
    reduction_percent: float
    download_url: str
    images: list[ImageSummary]


class HealthResponse(BaseModel):
    status: str


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


@router.get("/health", response_model=HealthResponse, summary="Check API availability")
@legacy_router.get("/api/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post(
    "/process",
    response_model=ProcessResponse,
    responses={400: {"model": ErrorResponse, "description": "Invalid input, image, destination, or filename collision."}},
    summary="Optimize and save a batch of images",
    description=(
        "Send multipart/form-data with an existing local output_folder, an entity_name, "
        "and at least one logo, cover, or gallery image. The folder path is on the "
        "machine running this local server. The response describes files saved there "
        "and supplies a temporary ZIP download URL."
    ),
)
@legacy_router.post("/api/process")
async def process_images(
    output_folder: Annotated[str, Form(description="Existing folder on the machine running the API")],
    entity_name: Annotated[str, Form(description="Event, company, or partner name")],
    naming_language: Annotated[str, Form(description="english or arabic")] = "english",
    include_brand_prefix: Annotated[bool, Form(description="Include the configured brand prefix in filenames")] = True,
    overwrite: Annotated[bool, Form(description="Replace images with matching generated filenames")] = False,
    logo_alt: Annotated[str | None, Form(description="Optional logo alt text; blank is allowed")] = None,
    cover_alt: Annotated[str | None, Form(description="Optional cover alt text; blank is allowed")] = None,
    gallery_alt: Annotated[str, Form(description="JSON array of gallery alt text strings, in upload order")] = "[]",
    logo: Annotated[UploadFile | None, File(description="One PNG, JPEG, WebP, or SVG logo")] = None,
    cover: Annotated[UploadFile | None, File(description="One PNG, JPEG, WebP, or SVG cover")] = None,
    gallery: Annotated[list[UploadFile], File(description="Repeat this field for gallery images")] = [],
) -> ProcessResponse:
    destination = Path(output_folder.strip()).expanduser()
    if not destination.is_dir():
        raise HTTPException(status_code=400, detail="Select a valid output folder.")
    if not entity_name.strip():
        raise HTTPException(status_code=400, detail="Enter an event, company, or partner name.")

    try:
        language = NamingLanguage(naming_language)
        gallery_alt_texts = _parse_gallery_alt_texts(gallery_alt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    uploads: list[UploadedImage] = []
    if logo is not None:
        uploads.append(await _to_uploaded_image(logo, ImageKind.LOGO, alt_text=logo_alt))
    if cover is not None:
        uploads.append(await _to_uploaded_image(cover, ImageKind.COVER, alt_text=cover_alt))
    for index, file in enumerate(gallery, start=1):
        alt_text = gallery_alt_texts[index - 1] if index <= len(gallery_alt_texts) else None
        uploads.append(await _to_uploaded_image(
            file, ImageKind.GALLERY, index=index, alt_text=alt_text
        ))

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
    _downloads[token] = (f"{slugify_name(entity_name)}.zip", result.zip_data)
    while len(_downloads) > DOWNLOAD_LIMIT:
        _downloads.popitem(last=False)

    metadata_by_name = {item.filename: item for item in result.seo_metadata}
    images = [
        ImageSummary(
            filename=image.output_path.name,
            alt_text=metadata_by_name[image.output_path.name].alt_text,
            original_bytes=image.original_bytes,
            output_bytes=image.output_bytes,
            original_size=image.original_size,
            output_size=image.output_size,
            reduction_percent=image.reduction_percent,
        )
        for image in result.images
    ]
    return ProcessResponse(
        message="Images have been saved successfully.",
        output_folder=str(result.output_folder.resolve()),
        original_bytes=result.original_bytes,
        output_bytes=result.output_bytes,
        reduction_percent=result.reduction_percent,
        download_url=f"/api/v1/download/{token}",
        images=images,
    )


@router.get(
    "/download/{token}",
    responses={
        200: {"content": {"application/zip": {}}, "description": "ZIP containing saved images and SEO CSV."},
        404: {"model": ErrorResponse, "description": "Download token is unknown or expired."},
    },
    summary="Download a processed batch",
)
@legacy_router.get("/api/download/{token}")
def download(token: str) -> StreamingResponse:
    item = _downloads.get(token)
    if item is None:
        raise HTTPException(status_code=404, detail="This download has expired.")
    filename, data = item
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(BytesIO(data), media_type="application/zip", headers=headers)
