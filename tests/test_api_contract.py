from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app import app
from ramworld_image_tool.api import download, legacy_router, process_images


def _cover_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1200, 800), "#1769aa").save(output, format="JPEG")
    return output.getvalue()


def _logo_upload() -> UploadFile:
    file = SpooledTemporaryFile(max_size=1024 * 1024)
    file.write(_cover_bytes())
    file.seek(0)
    return UploadFile(file=file, filename="logo.jpg")


def _run_in_memory_upload(coroutine):
    """The in-memory UploadFile path completes without scheduling an event loop."""
    with pytest.raises(StopIteration) as finished:
        coroutine.send(None)
    return finished.value.value


def test_openapi_documents_v1_and_hides_compatibility_routes() -> None:
    schema = app.openapi()
    paths = schema["paths"]

    assert app.version == "1.0.0"
    assert "/api/v1/health" in paths
    assert "/api/v1/process" in paths
    assert "/api/v1/download/{token}" in paths
    assert "/api/process" not in paths
    assert "/api/select-folder" not in paths
    assert "400" in paths["/api/v1/process"]["post"]["responses"]
    assert "404" in paths["/api/v1/download/{token}"]["get"]["responses"]
    assert any(route.path == "/api/process" for route in legacy_router.routes)


def test_versioned_handler_returns_documented_result_and_download(tmp_path: Path) -> None:
    logo = _logo_upload()
    result = _run_in_memory_upload(process_images(
        output_folder=str(tmp_path),
        entity_name="Example Event",
        naming_language="english",
        include_brand_prefix=True,
        overwrite=False,
        logo_alt="Example Event logo",
        cover_alt=None,
        gallery_alt="[]",
        logo=logo,
        cover=None,
        gallery=[],
    ))

    assert result.download_url.startswith("/api/v1/download/")
    assert result.images[0].filename == "ramworld-example-event-logo.jpg"
    assert result.images[0].alt_text == "Example Event logo"
    assert (tmp_path / "example-event" / result.images[0].filename).is_file()
    token = result.download_url.rsplit("/", 1)[1]
    assert download(token).media_type == "application/zip"


def test_versioned_handler_reports_bad_destination(tmp_path: Path) -> None:
    with pytest.raises(HTTPException) as error:
        _run_in_memory_upload(process_images(
            output_folder=str(tmp_path / "missing"),
            entity_name="Example Event",
            naming_language="english",
            include_brand_prefix=True,
            overwrite=False,
            logo_alt=None,
            cover_alt=None,
            gallery_alt="[]",
            logo=_logo_upload(),
            cover=None,
            gallery=[],
        ))
    assert error.value.status_code == 400
    assert error.value.detail == "Select a valid output folder."
