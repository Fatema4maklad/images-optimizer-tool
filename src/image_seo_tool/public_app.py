"""ASGI entry point for the separate, simple public image interface."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .public_service import PublicService, PublicSettings
from .version import __version__


WEB_DIR = Path(__file__).resolve().parent / "public_web"
SHARED_WEB_DIR = Path(__file__).resolve().parent / "i18n"


class RequestTooLarge(Exception):
    pass


class UploadSizeLimit:
    """Reject oversized HTTP bodies before multipart parsing."""

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("path") != "/api/public/process" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                size = int(declared)
            except ValueError:
                size = -1
            if size < 0 or size > self.max_bytes:
                await JSONResponse({"detail": "Upload request is too large."}, status_code=413)(scope, receive, send)
                return

        received = 0
        started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise RequestTooLarge()
            return message

        async def tracked_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except RequestTooLarge:
            if started:
                raise
            await JSONResponse({"detail": "Upload request is too large."}, status_code=413)(scope, receive, send)


def create_public_app(settings: PublicSettings | None = None) -> FastAPI:
    """Create the new interface without changing the existing local app."""
    selected = settings or PublicSettings.from_env()
    service = PublicService(selected)
    app = FastAPI(title="Image Optimizer", version=__version__)
    app.add_middleware(UploadSizeLimit, max_bytes=selected.max_request_bytes)
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")
    app.mount("/i18n", StaticFiles(directory=SHARED_WEB_DIR), name="i18n")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/api/public/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/public/process")
    async def process_endpoint(
        project_name: str = Form(...),
        filename_prefix: str = Form(""),
        naming_language: str = Form("english"),
        images: list[UploadFile] = File(...),
    ) -> dict:
        return await service.process(project_name, filename_prefix, naming_language, images)

    @app.get("/api/public/download/{token}")
    def download_all(token: str) -> FileResponse:
        return FileResponse(
            service.archive(token), media_type="application/zip", filename="optimized-images.zip",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/api/public/preview/{token}/{filename}")
    def preview(token: str, filename: str) -> StreamingResponse:
        return StreamingResponse(
            BytesIO(service.image(token, filename)), media_type="image/webp",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    @app.get("/api/public/download/{token}/{filename}")
    def download_one(token: str, filename: str) -> StreamingResponse:
        return StreamingResponse(
            BytesIO(service.image(token, filename)), media_type="image/webp",
            headers={
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            },
        )

    return app
