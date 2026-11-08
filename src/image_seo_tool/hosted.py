"""Authenticated API for processing uploads from another system.

Run with ``uvicorn image_seo_tool.hosted:create_hosted_app --factory``.
The local browser app remains a separate application in ``app.py``.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Response, Security, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from .api_models import ErrorResponse, HealthResponse, ImageSummary
from .batch import save_processed_result
from .config import ToolConfig
from .core import UploadedImage, process_images
from .download_store import DownloadStore
from .http_common import parse_gallery_alt_texts, summarize_images
from .naming import ImageKind, NamingLanguage
from .version import __version__


class RequestTooLarge(Exception):
    pass


@dataclass(frozen=True, slots=True)
class HostedSettings:
    storage_root: Path
    api_token: str = field(repr=False)
    max_request_bytes: int = 32 * 1024 * 1024
    max_file_bytes: int = 10 * 1024 * 1024
    max_files: int = 12
    max_image_pixels: int = 20_000_000
    max_project_bytes: int = 64 * 1024 * 1024
    download_ttl_seconds: int = 3600

    def __post_init__(self) -> None:
        root = Path(self.storage_root).expanduser()
        if not root.is_absolute():
            raise ValueError("Hosted storage root must be an absolute path.")
        object.__setattr__(self, "storage_root", root.resolve())
        if len(self.api_token) < 32 or any(character.isspace() for character in self.api_token):
            raise ValueError("Hosted API token must contain at least 32 non-space characters.")
        if self.max_request_bytes < 1 or self.max_file_bytes < 1:
            raise ValueError("Upload limits must be positive.")
        if self.max_file_bytes > self.max_request_bytes:
            raise ValueError("Per-file limit cannot exceed the request limit.")
        if (
            self.max_files < 1 or self.max_image_pixels < 1
            or self.max_project_bytes < 1 or self.download_ttl_seconds < 1
        ):
            raise ValueError("Hosted limits and download lifetime must be positive.")

    @classmethod
    def from_env(cls) -> HostedSettings:
        root = os.environ.get("IMAGE_SEO_STORAGE_ROOT")
        token = os.environ.get("IMAGE_SEO_API_TOKEN")
        if not root or not token:
            raise ValueError(
                "Set IMAGE_SEO_STORAGE_ROOT and IMAGE_SEO_API_TOKEN "
                "before starting the hosted API."
            )
        return cls(
            storage_root=Path(root),
            api_token=token,
            max_request_bytes=int(os.environ.get("IMAGE_SEO_MAX_REQUEST_BYTES", 32 * 1024 * 1024)),
            max_file_bytes=int(os.environ.get("IMAGE_SEO_MAX_FILE_BYTES", 10 * 1024 * 1024)),
            max_files=int(os.environ.get("IMAGE_SEO_MAX_FILES", 12)),
            max_image_pixels=int(os.environ.get("IMAGE_SEO_MAX_IMAGE_PIXELS", 20_000_000)),
            max_project_bytes=int(os.environ.get("IMAGE_SEO_MAX_PROJECT_BYTES", 64 * 1024 * 1024)),
            download_ttl_seconds=int(os.environ.get("IMAGE_SEO_DOWNLOAD_TTL_SECONDS", 3600)),
        )


class HostedGate:
    """Reject unauthorized and oversized requests before multipart parsing."""

    def __init__(self, app, settings: HostedSettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if not path.startswith("/api/v2/") or path == "/api/v2/health":
            await self.app(scope, receive, send)
            return

        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("ascii", errors="ignore")
        scheme, separator, token = authorization.partition(" ")
        authorized = (
            separator
            and scheme.lower() == "bearer"
            and hmac.compare_digest(token, self.settings.api_token)
        )
        if not authorized:
            await JSONResponse(
                {"detail": "Authentication required."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )(scope, receive, send)
            return

        if path != "/api/v2/process" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = -1
            if declared_size < 0:
                await JSONResponse(
                    {"detail": "Invalid Content-Length."}, status_code=400
                )(scope, receive, send)
                return
            if declared_size > self.settings.max_request_bytes:
                await JSONResponse(
                    {"detail": "Request is too large."}, status_code=413
                )(scope, receive, send)
                return

        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.settings.max_request_bytes:
                    raise RequestTooLarge()
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestTooLarge:
            if response_started:
                raise
            await JSONResponse(
                {"detail": "Request is too large."}, status_code=413
            )(scope, receive, send)


class HostedProcessResponse(BaseModel):
    project_slug: str
    original_bytes: int
    output_bytes: int
    reduction_percent: float
    download_url: str
    images: list[ImageSummary]


class HostedService:
    def __init__(self, settings: HostedSettings) -> None:
        self.settings = settings
        settings.storage_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.downloads = DownloadStore(
            settings.storage_root / ".downloads", settings.download_ttl_seconds
        )

    async def _read_upload(
        self, file: UploadFile, kind: ImageKind, index: int | None, alt_text: str | None
    ) -> UploadedImage:
        data = bytearray()
        while True:
            chunk = await file.read(min(64 * 1024, self.settings.max_file_bytes - len(data) + 1))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > self.settings.max_file_bytes:
                raise HTTPException(
                    status_code=413,
                    detail="An image exceeds the per-file upload limit.",
                )
        return UploadedImage(file.filename or "image", bytes(data), kind, index, alt_text)

    async def process(
        self,
        entity_name: str,
        naming_language: str,
        filename_prefix: str,
        overwrite: bool,
        logo_alt: str | None,
        cover_alt: str | None,
        gallery_alt: str,
        logo: UploadFile | None,
        cover: UploadFile | None,
        gallery: list[UploadFile],
    ) -> HostedProcessResponse:
        files = int(logo is not None) + int(cover is not None) + len(gallery)
        if files < 1:
            raise HTTPException(status_code=400, detail="Upload at least one image.")
        if files > self.settings.max_files:
            raise HTTPException(status_code=413, detail="Too many images in one request.")
        try:
            language = NamingLanguage(naming_language)
            alt_texts = parse_gallery_alt_texts(gallery_alt)
            config = ToolConfig(
                naming_language=language,
                filename_prefix=filename_prefix,
                max_pixels=self.settings.max_image_pixels,
                preserve_original_bytes=False,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        uploads: list[UploadedImage] = []
        if logo is not None:
            uploads.append(await self._read_upload(logo, ImageKind.LOGO, None, logo_alt))
        if cover is not None:
            uploads.append(await self._read_upload(cover, ImageKind.COVER, None, cover_alt))
        for index, file in enumerate(gallery, start=1):
            alt_text = alt_texts[index - 1] if index <= len(alt_texts) else None
            uploads.append(await self._read_upload(file, ImageKind.GALLERY, index, alt_text))

        try:
            processed = process_images(entity_name, uploads, config=config)
            if any(asset.mime_type == "image/svg+xml" for asset in processed.assets):
                raise HTTPException(
                    status_code=415,
                    detail="SVG uploads are not supported by the hosted API.",
                )
            project_folder = self.settings.storage_root / processed.slug
            previous_bytes = 0
            replaced_bytes = 0
            if project_folder.is_dir():
                previous_bytes = sum(
                    path.stat().st_size
                    for path in project_folder.iterdir()
                    if path.is_file()
                )
                replaced_bytes = sum(
                    (project_folder / asset.filename).stat().st_size
                    for asset in processed.assets
                    if (project_folder / asset.filename).is_file()
                )
            projected_bytes = previous_bytes - replaced_bytes + processed.output_bytes
            if projected_bytes > self.settings.max_project_bytes:
                raise HTTPException(
                    status_code=413, detail="The project exceeds its storage limit."
                )
            result = save_processed_result(
                processed, self.settings.storage_root, overwrite=overwrite
            )
        except (ValueError, FileExistsError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        token = self.downloads.create(result.zip_data)
        return HostedProcessResponse(
            project_slug=processed.slug,
            original_bytes=result.original_bytes,
            output_bytes=result.output_bytes,
            reduction_percent=result.reduction_percent,
            download_url=f"/api/v2/download/{token}",
            images=summarize_images(result),
        )

    def download(self, token: str) -> FileResponse:
        path = self.downloads.get(token)
        if path is None:
            raise HTTPException(status_code=404, detail="This download has expired.")
        return FileResponse(
            path,
            media_type="application/zip",
            filename="optimized-images.zip",
            headers={"Cache-Control": "no-store"},
        )


def create_hosted_app(settings: HostedSettings | None = None) -> FastAPI:
    """Create a hosted-only app; local folder routes are never mounted here."""
    selected = settings or HostedSettings.from_env()
    service = HostedService(selected)
    app = FastAPI(title="Image SEO Hosted API", version=__version__)
    protected = APIRouter(prefix="/api/v2", tags=["images"], dependencies=[Security(HTTPBearer())])

    @app.get("/api/v2/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @protected.post(
        "/process",
        response_model=HostedProcessResponse,
        responses={
            400: {"model": ErrorResponse, "description": "Invalid image or request."},
            401: {"model": ErrorResponse, "description": "Authentication required."},
            413: {"model": ErrorResponse, "description": "Request, file, or count limit exceeded."},
            415: {"model": ErrorResponse, "description": "SVG is not accepted by the hosted API."},
        },
    )
    async def process_endpoint(
        response: Response,
        entity_name: Annotated[str, Form(description="Project name")],
        naming_language: Annotated[str, Form()] = "english",
        filename_prefix: Annotated[str, Form()] = "",
        overwrite: Annotated[bool, Form()] = False,
        logo_alt: Annotated[str | None, Form()] = None,
        cover_alt: Annotated[str | None, Form()] = None,
        gallery_alt: Annotated[str, Form()] = "[]",
        logo: Annotated[UploadFile | None, File()] = None,
        cover: Annotated[UploadFile | None, File()] = None,
        gallery: Annotated[list[UploadFile], File()] = [],
    ) -> HostedProcessResponse:
        result = await service.process(
            entity_name, naming_language, filename_prefix, overwrite,
            logo_alt, cover_alt, gallery_alt, logo, cover, gallery,
        )
        response.headers["Cache-Control"] = "no-store"
        return result

    @protected.get(
        "/download/{token}",
        responses={
            200: {"content": {"application/zip": {}}, "description": "Temporary ZIP download."},
            401: {"model": ErrorResponse, "description": "Authentication required."},
            404: {"model": ErrorResponse, "description": "Unknown or expired download."},
        },
    )
    def download_endpoint(token: str) -> FileResponse:
        return service.download(token)

    app.include_router(protected)
    app.add_middleware(HostedGate, settings=selected)
    app.state.hosted_service = service
    return app
