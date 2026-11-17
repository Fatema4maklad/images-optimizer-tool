"""Behavior at the new public boundary, including rejected inputs."""

import os
import time
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile
from zipfile import ZipFile

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image

from image_seo_tool.public_app import UploadSizeLimit, create_public_app
from image_seo_tool.public_service import PublicService, PublicSettings


def immediate(coroutine):
    with pytest.raises(StopIteration) as finished:
        coroutine.send(None)
    return finished.value.value


def upload(data: bytes, name: str = "source.jpg") -> UploadFile:
    file = SpooledTemporaryFile(max_size=1024 * 1024)
    file.write(data)
    file.seek(0)
    return UploadFile(file=file, filename=name)


def jpeg(size=(24, 18)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, "#2072b9").save(output, format="JPEG")
    return output.getvalue()


def service(tmp_path: Path, **limits) -> PublicService:
    return PublicService(PublicSettings(tmp_path, **limits))


def process(selected: PublicService, images, name="Example Event", prefix="", language="english"):
    return immediate(selected.process(name, prefix, language, images))


def test_public_result_has_generic_names_previews_and_individual_downloads(tmp_path):
    selected = service(tmp_path)
    result = process(selected, [upload(jpeg()), upload(jpeg(), "second.png")])
    assert [item["filename"] for item in result["images"]] == [
        "example-event-01.webp", "example-event-02.webp"
    ]
    assert result["images"][0]["preview_url"].startswith("/api/public/preview/")
    for item in result["images"]:
        data = selected.image(result["download_all_url"].rsplit("/", 1)[1], item["filename"])
        with Image.open(BytesIO(data)) as image:
            assert image.format == "WEBP"
    archive = selected.archive(result["download_all_url"].rsplit("/", 1)[1])
    with ZipFile(archive) as zip_file:
        assert set(zip_file.namelist()) == {
            "example-event/example-event-01.webp",
            "example-event/example-event-02.webp",
            "example-event/example-event-image-seo.csv",
        }
        csv = zip_file.read("example-event/example-event-image-seo.csv").decode("utf-8-sig")
        assert "example-event-01.webp" in csv
        assert "Image 1 from Example Event" in csv


def test_optional_prefix_and_arabic_project_are_preserved(tmp_path):
    result = process(service(tmp_path), [upload(jpeg())], name="فعالية الرياض", prefix="My Brand", language="arabic")
    assert result["images"][0]["filename"] == "my-brand-فعالية-الرياض-01.webp"
    assert result["images"][0]["alt_text"] == "صورة 1 من فعالية الرياض"


@pytest.mark.parametrize("name,images,prefix,language,status", [
    ("Example", [], "", "english", 400),
    ("  ", [upload(jpeg())], "", "english", 400),
    ("Example", [upload(jpeg())], "!!!", "english", 400),
    ("Example", [upload(jpeg())], "", "unknown", 400),
    ("Example", [upload(b"invalid")], "", "english", 400),
    ("Example", [upload(jpeg(), "sample.svg")], "", "english", 415),
    ("Example", [upload(b"", "empty.jpg")], "", "english", 413),
    ("x" * 121, [upload(jpeg())], "", "english", 400),
    ("Example", [upload(jpeg())], "x" * 81, "english", 400),
    ("界" * 90, [upload(jpeg())], "", "english", 400),
])
def test_bad_requests_return_clear_http_errors(tmp_path, name, images, prefix, language, status):
    with pytest.raises(HTTPException) as failure:
        process(service(tmp_path), images, name, prefix, language)
    assert failure.value.status_code == status
    assert failure.value.detail


def test_size_count_and_pixel_limits(tmp_path):
    with pytest.raises(HTTPException) as too_large:
        process(service(tmp_path, max_file_bytes=100), [upload(jpeg())])
    assert too_large.value.status_code == 413
    with pytest.raises(HTTPException) as too_many:
        process(service(tmp_path, max_files=2), [upload(jpeg()) for _ in range(3)])
    assert too_many.value.status_code == 400
    with pytest.raises(HTTPException) as pixels:
        process(service(tmp_path, max_pixels=100), [upload(jpeg())])
    assert pixels.value.status_code == 400
    with pytest.raises(HTTPException) as archive:
        process(service(tmp_path, max_zip_bytes=10), [upload(jpeg())])
    assert archive.value.status_code == 413


def test_download_token_and_filename_cannot_select_other_files(tmp_path):
    selected = service(tmp_path)
    result = process(selected, [upload(jpeg())])
    token = result["download_all_url"].rsplit("/", 1)[1]
    for bad_token, name in [("bad", "example-event-01.webp"), (token, "other.webp"), (token, "../example-event-01.webp")]:
        with pytest.raises(HTTPException) as failure:
            selected.image(bad_token, name)
        assert failure.value.status_code == 404


def test_expired_result_is_removed(tmp_path):
    selected = service(tmp_path, download_ttl_seconds=1)
    result = process(selected, [upload(jpeg())])
    token = result["download_all_url"].rsplit("/", 1)[1]
    path = selected.archive(token)
    old = time.time() - 5
    os.utime(path, (old, old))
    with pytest.raises(HTTPException) as failure:
        selected.archive(token)
    assert failure.value.status_code == 404
    assert not path.exists()


def test_http_body_limit_rejects_declared_and_streamed_oversize():
    called = []

    async def inner(scope, receive, send):
        called.append(True)
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def request(headers, body):
        messages = []
        scope = {"type": "http", "method": "POST", "path": "/api/public/process", "headers": headers}

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        await UploadSizeLimit(inner, 4)(scope, receive, send)
        return messages[0]["status"]

    assert immediate(request([(b"content-length", b"5")], b"12345")) == 413
    assert not called
    assert immediate(request([], b"12345")) == 413
    assert called == [True]
    assert immediate(request([], b"1234")) == 200


def test_public_app_exposes_one_upload_field_and_no_local_folder(tmp_path):
    app = create_public_app(PublicSettings(tmp_path))
    schema = app.openapi()
    body = schema["paths"]["/api/public/process"]["post"]["requestBody"]
    ref = body["content"]["multipart/form-data"]["schema"]["$ref"]
    fields = schema["components"]["schemas"][ref.rsplit("/", 1)[1]]["properties"]
    assert "images" in fields
    assert all(field not in fields for field in ("logo", "cover", "gallery", "output_folder"))
    assert "/api/public/download/{token}/{filename}" in schema["paths"]


def test_public_page_serves_bilingual_ui(tmp_path):
    client = TestClient(create_public_app(PublicSettings(tmp_path)))
    page = client.get("/")
    assert page.status_code == 200
    assert 'data-interface-language="ar"' in page.text
    assert client.get("/i18n/strings.js").status_code == 200
