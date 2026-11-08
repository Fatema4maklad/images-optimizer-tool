from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image

import app as app_module
from app import app


client = TestClient(app)


def image_bytes(format_name: str = "PNG", size: tuple[int, int] = (900, 600)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (44, 105, 190)).save(output, format=format_name)
    return output.getvalue()


def test_normal_web_interface_contains_in_field_previews_and_theme_switch() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Image SEO Optimizer" in response.text
    assert 'id="theme-toggle"' in response.text
    assert 'name="filename_prefix"' in response.text
    assert 'Times New Roman' in client.get("/assets/styles.css").text
    assert 'id="logo-drop-zone"' in response.text
    assert 'class="preview-area"' in response.text
    assert 'data-add="gallery"' in response.text
    assert 'id="preview-dialog"' in response.text
    assert "SEO alt text" in response.text
    assert "made by Eng. Fatem ★" in response.text

    css = client.get("/assets/styles.css")
    assert css.status_code == 200
    assert '[data-theme="dark"]' in css.text
    assert ".drop-zone.has-files .preview-area" in css.text
    assert ".remove-image" in css.text
    assert "overflow-y: auto" in css.text

    javascript = client.get("/assets/app.js")
    assert javascript.status_code == 200
    assert "URL.createObjectURL" in javascript.text
    assert 'zone.classList.toggle("has-files"' in javascript.text
    assert 'localStorage.setItem("image-seo-tool-theme"' in javascript.text
    assert "data-remove-kind" in javascript.text
    assert "showImagePreview" in javascript.text


def test_mac_launcher_bootstraps_and_starts_the_app() -> None:
    launcher = Path(__file__).parents[1] / "start_app.command"
    contents = launcher.read_text(encoding="utf-8")

    assert contents.startswith("#!/bin/bash")
    assert 'MAC_ENV=".venv-mac"' in contents
    assert "python3 -m venv" in contents
    assert 'pip install -e ".[web]"' in contents
    assert "open \"http://127.0.0.1:8765/" in contents


def test_mac_folder_picker_uses_osascript(monkeypatch) -> None:
    completed = SimpleNamespace(returncode=0, stdout="/Users/shooq/Pictures/\n", stderr="")
    monkeypatch.setattr(app_module.sys, "platform", "darwin")
    monkeypatch.setattr(app_module.subprocess, "run", lambda *args, **kwargs: completed)

    assert app_module._pick_output_folder() == "/Users/shooq/Pictures/"


def test_process_endpoint_saves_and_returns_download(tmp_path: Path) -> None:
    response = client.post(
        "/api/v1/process",
        data={
            "output_folder": str(tmp_path),
            "entity_name": "Riyadh Forum",
            "naming_language": "english",
            "overwrite": "false",
            "logo_alt": "Riyadh Forum logo",
            "cover_alt": "Riyadh Forum cover",
            "gallery_alt": '["Riyadh Forum audience"]',
        },
        files=[
            ("logo", ("logo.png", image_bytes(), "image/png")),
            ("cover", ("cover.jpg", image_bytes("JPEG"), "image/jpeg")),
            ("gallery", ("audience.jpg", image_bytes("JPEG"), "image/jpeg")),
        ],
    )

    assert response.status_code == 200
    result = response.json()
    assert result["message"] == "Images have been saved successfully."
    assert len(result["images"]) == 3
    assert result["images"][0]["filename"].endswith("-logo.png")
    assert result["images"][1]["filename"].endswith("-cover.webp")
    assert result["images"][2]["filename"].endswith("-gallery-01.webp")
    assert Path(result["output_folder"]).is_dir()

    download = client.get(result["download_url"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(download.content)) as archive:
        names = archive.namelist()
    assert any(name.endswith("-logo.png") for name in names)
    assert any(name.endswith("-image-seo.csv") for name in names)


def test_process_endpoint_requires_a_valid_destination(tmp_path: Path) -> None:
    response = client.post(
        "/api/v1/process",
        data={
            "output_folder": str(tmp_path / "missing"),
            "entity_name": "Event",
        },
        files={"logo": ("logo.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Select a valid output folder."


def test_process_endpoint_accepts_custom_prefix(tmp_path: Path) -> None:
    response = client.post(
        "/api/process",
        data={
            "output_folder": str(tmp_path),
            "entity_name": "Riyadh Forum",
            "naming_language": "english",
            "filename_prefix": "My Brand",
        },
        files={"logo": ("logo.png", image_bytes(), "image/png")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["images"][0]["filename"] == "my-brand-riyadh-forum-logo.png"
    assert Path(result["output_folder"], "riyadh-forum-image-seo.csv").is_file()
