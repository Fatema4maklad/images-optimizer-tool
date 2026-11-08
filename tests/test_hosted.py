import os
import time
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from image_seo_tool import ImageKind, ToolConfig, UploadedImage, process_images
from image_seo_tool.download_store import DownloadStore
from image_seo_tool.hosted import HostedGate, HostedService, HostedSettings, create_hosted_app
from image_seo_tool.version import __version__


def _run_immediate(coroutine):
    with pytest.raises(StopIteration) as finished:
        coroutine.send(None)
    return finished.value.value


def _upload(data: bytes, filename: str = "image.jpg") -> UploadFile:
    file = SpooledTemporaryFile(max_size=1024 * 1024)
    file.write(data)
    file.seek(0)
    return UploadFile(file=file, filename=filename)


def _jpeg(size: tuple[int, int] = (1200, 800)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, "#1769aa").save(output, format="JPEG")
    return output.getvalue()


def _settings(root: Path, **overrides) -> HostedSettings:
    return HostedSettings(storage_root=root, api_token="t" * 32, **overrides)


def _process(service: HostedService, image: UploadFile):
    return service.process(
        "Example Event", "english", "My Brand", False,
        None, None, "[]", None, image, [],
    )


def test_hosted_config_requires_explicit_root_and_strong_token(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="absolute path"):
        HostedSettings(Path("relative"), "t" * 32)
    with pytest.raises(ValueError, match="at least 32"):
        HostedSettings(tmp_path, "short")
    settings = _settings(tmp_path)
    assert "t" * 32 not in repr(settings)


def test_hosted_config_reads_required_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("IMAGE_SEO_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("IMAGE_SEO_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="IMAGE_SEO_STORAGE_ROOT"):
        HostedSettings.from_env()

    monkeypatch.setenv("IMAGE_SEO_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("IMAGE_SEO_API_TOKEN", "x" * 32)
    settings = HostedSettings.from_env()
    assert settings.storage_root == tmp_path.resolve()


def test_hosted_openapi_has_bearer_auth_and_no_local_folder_route(tmp_path: Path) -> None:
    app = create_hosted_app(_settings(tmp_path))
    schema = app.openapi()
    assert app.version == __version__
    assert "/api/v2/process" in schema["paths"]
    assert "/api/v2/download/{token}" in schema["paths"]
    assert "/api/v1/process" not in schema["paths"]
    assert "/api/select-folder" not in schema["paths"]
    body = schema["paths"]["/api/v2/process"]["post"]["requestBody"]
    form_schema = body["content"]["multipart/form-data"]["schema"]
    form_fields = schema["components"]["schemas"][form_schema["$ref"].rsplit("/", 1)[1]]["properties"]
    assert "output_folder" not in form_fields
    assert "HTTPBearer" in schema["components"]["securitySchemes"]


def test_hosted_processing_uses_controlled_root_and_disk_download(tmp_path: Path) -> None:
    service = HostedService(_settings(tmp_path))
    source = _jpeg()
    result = _run_immediate(_process(service, _upload(source)))

    assert result.project_slug == "example-event"
    assert result.images[0].filename == "my-brand-example-event-cover.webp"
    saved_path = tmp_path / "example-event" / result.images[0].filename
    expected = process_images(
        "Example Event",
        [UploadedImage("image.jpg", source, ImageKind.COVER)],
        config=ToolConfig(
            filename_prefix="My Brand",
            max_pixels=20_000_000,
            preserve_original_bytes=False,
        ),
    )
    assert saved_path.read_bytes() == expected.assets[0].data
    token = result.download_url.rsplit("/", 1)[1]
    assert service.downloads.get(token) == tmp_path / ".downloads" / f"{token}.zip"
    assert service.download(token).media_type == "application/zip"
    assert "output_folder" not in result.model_dump()


def test_hosted_rejects_large_files_pixels_and_svg_before_saving(tmp_path: Path) -> None:
    service = HostedService(_settings(tmp_path, max_file_bytes=100, max_image_pixels=10_000))
    with pytest.raises(HTTPException) as large:
        _run_immediate(_process(service, _upload(_jpeg())))
    assert large.value.status_code == 413

    pixel_service = HostedService(_settings(tmp_path, max_image_pixels=10_000))
    with pytest.raises(HTTPException) as pixels:
        _run_immediate(_process(pixel_service, _upload(_jpeg())))
    assert pixels.value.status_code == 400
    assert "pixel count" in pixels.value.detail

    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"/>'
    with pytest.raises(HTTPException) as vector:
        _run_immediate(_process(pixel_service, _upload(svg, "image.svg")))
    assert vector.value.status_code == 415
    assert not (tmp_path / "example-event").exists()


def test_hosted_project_quota_rejects_output_before_saving(tmp_path: Path) -> None:
    service = HostedService(_settings(tmp_path, max_project_bytes=100))
    with pytest.raises(HTTPException) as error:
        _run_immediate(_process(service, _upload(_jpeg())))
    assert error.value.status_code == 413
    assert "storage limit" in error.value.detail
    assert not (tmp_path / "example-event").exists()


def test_download_store_expires_and_removes_old_zip(tmp_path: Path) -> None:
    store = DownloadStore(tmp_path / "downloads", ttl_seconds=60)
    token = store.create(b"zip data")
    path = store.get(token)
    assert path is not None
    os.utime(path, (time.time() - 120, time.time() - 120))
    assert store.get(token) is None
    assert not path.exists()


def test_guard_rejects_unauthorized_and_oversized_requests_early(tmp_path: Path) -> None:
    settings = _settings(tmp_path, max_request_bytes=10, max_file_bytes=10)
    called = []
    sent = []

    async def downstream(scope, receive, send):
        called.append(True)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    gate = HostedGate(downstream, settings)
    scope = {"type": "http", "path": "/api/v2/process", "method": "POST", "headers": []}
    _run_immediate(gate(scope, receive, send))
    assert sent[0]["status"] == 401
    assert not called

    sent.clear()
    scope["headers"] = [(b"authorization", b"Bearer " + settings.api_token.encode()), (b"content-length", b"11")]
    _run_immediate(gate(scope, receive, send))
    assert sent[0]["status"] == 413
    assert not called


def test_guard_limits_stream_without_content_length(tmp_path: Path) -> None:
    settings = _settings(tmp_path, max_request_bytes=10, max_file_bytes=10)
    sent = []
    chunks = [b"123456", b"789012"]

    async def downstream(scope, receive, send):
        await receive()
        await receive()

    async def receive():
        return {"type": "http.request", "body": chunks.pop(0), "more_body": bool(chunks)}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http", "path": "/api/v2/process", "method": "POST",
        "headers": [(b"authorization", b"Bearer " + settings.api_token.encode())],
    }
    _run_immediate(HostedGate(downstream, settings)(scope, receive, send))
    assert sent[0]["status"] == 413
