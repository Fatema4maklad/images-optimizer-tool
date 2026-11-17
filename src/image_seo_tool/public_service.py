"""Processing and short-lived downloads for the simple public interface."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException, UploadFile

from .config import ToolConfig
from .core import ProcessingResult, UploadedImage, process_images
from .download_store import DownloadStore
from .naming import ImageKind, NamingLanguage, slugify_name


@dataclass(frozen=True, slots=True)
class PublicSettings:
    storage_root: Path
    max_request_bytes: int = 32 * 1024 * 1024
    max_file_bytes: int = 10 * 1024 * 1024
    max_files: int = 12
    max_pixels: int = 20_000_000
    max_zip_bytes: int = 64 * 1024 * 1024
    download_ttl_seconds: int = 3600

    def __post_init__(self) -> None:
        root = Path(self.storage_root).expanduser()
        if not root.is_absolute():
            raise ValueError("Public storage root must be an absolute path.")
        object.__setattr__(self, "storage_root", root.resolve())
        limits = (
            self.max_request_bytes, self.max_file_bytes, self.max_files,
            self.max_pixels, self.max_zip_bytes, self.download_ttl_seconds,
        )
        if min(limits) < 1 or self.max_file_bytes > self.max_request_bytes:
            raise ValueError("Public limits must be positive and internally consistent.")

    @classmethod
    def from_env(cls) -> PublicSettings:
        root = os.environ.get("IMAGE_SEO_PUBLIC_STORAGE_ROOT")
        if not root:
            raise ValueError("Set IMAGE_SEO_PUBLIC_STORAGE_ROOT before starting the public app.")
        return cls(storage_root=Path(root))


def build_download_zip(processed: ProcessingResult) -> bytes:
    """Package one isolated request, without a shared project directory."""
    metadata = StringIO(newline="")
    writer = csv.writer(metadata)
    writer.writerow(("filename", "alt_text", "url_encoded_filename", "html_example"))
    for item in processed.seo_metadata:
        writer.writerow((item.filename, item.alt_text, item.url_encoded_filename, item.html_example))

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for asset in processed.assets:
            archive.writestr(f"{processed.slug}/{asset.filename}", asset.data)
        archive.writestr(
            f"{processed.slug}/{processed.slug}-image-seo.csv",
            metadata.getvalue().encode("utf-8-sig"),
        )
    return output.getvalue()


class PublicService:
    def __init__(self, settings: PublicSettings) -> None:
        self.settings = settings
        self.downloads = DownloadStore(
            settings.storage_root / ".downloads", settings.download_ttl_seconds
        )

    async def process(
        self, project_name: str, filename_prefix: str,
        naming_language: str, images: list[UploadFile],
    ) -> dict:
        if not 1 <= len(images) <= self.settings.max_files:
            raise HTTPException(status_code=400, detail=f"Choose between one and {self.settings.max_files} images.")
        try:
            language = NamingLanguage(naming_language)
            config = ToolConfig(
                naming_language=language,
                filename_prefix=filename_prefix,
                include_kind_label=False,
                max_pixels=self.settings.max_pixels,
                preserve_original_bytes=False,
            )
            clean_name = project_name.strip()
            if len(clean_name) > 120 or len(filename_prefix) > 80:
                raise ValueError("Project name or filename prefix is too long.")
            stem = f"{config.filename_prefix + '-' if config.filename_prefix else ''}{slugify_name(clean_name)}"
            if len(f"{stem}-{self.settings.max_files:02d}.webp".encode("utf-8")) > 240:
                raise ValueError("The generated filename is too long.")
            uploads = []
            for index, image in enumerate(images, start=1):
                if Path(image.filename or "").suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                    raise HTTPException(status_code=415, detail="Use JPEG, PNG, or WebP images.")
                data = await image.read(self.settings.max_file_bytes + 1)
                if not data or len(data) > self.settings.max_file_bytes:
                    raise HTTPException(status_code=413, detail="An image is empty or too large.")
                alt_text = (
                    f"صورة {index} من {clean_name}"
                    if language is NamingLanguage.ARABIC
                    else f"Image {index} from {clean_name}"
                )
                uploads.append(UploadedImage(
                    image.filename or "image", data, ImageKind.GALLERY,
                    gallery_index=index, alt_text=alt_text,
                ))
            processed = process_images(clean_name, uploads, config=config)
            if any(asset.mime_type != "image/webp" for asset in processed.assets):
                raise HTTPException(status_code=415, detail="Use JPEG, PNG, or WebP images.")
            archive = build_download_zip(processed)
            if len(archive) > self.settings.max_zip_bytes:
                raise HTTPException(status_code=413, detail="The result is too large to download.")
            token = self.downloads.create(archive)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "project_name": clean_name,
            "original_bytes": processed.original_bytes,
            "output_bytes": processed.output_bytes,
            "reduction_percent": processed.reduction_percent,
            "download_all_url": f"/api/public/download/{token}",
            "images": [
                {
                    "filename": asset.filename,
                    "alt_text": asset.alt_text,
                    "original_bytes": asset.original_bytes,
                    "output_bytes": asset.output_bytes,
                    "original_size": asset.original_size,
                    "output_size": asset.output_size,
                    "preview_url": f"/api/public/preview/{token}/{quote(asset.filename)}",
                    "download_url": f"/api/public/download/{token}/{quote(asset.filename)}",
                }
                for asset in processed.assets
            ],
        }

    def archive(self, token: str) -> Path:
        path = self.downloads.get(token)
        if path is None:
            raise HTTPException(status_code=404, detail="This download has expired.")
        return path

    def image(self, token: str, filename: str) -> bytes:
        if Path(filename).name != filename or not filename.endswith(".webp"):
            raise HTTPException(status_code=404, detail="Image not found.")
        with ZipFile(self.archive(token)) as archive:
            matches = [
                name for name in archive.namelist()
                if name.count("/") == 1 and name.endswith("/" + filename)
            ]
            if len(matches) != 1:
                raise HTTPException(status_code=404, detail="Image not found.")
            entry = archive.getinfo(matches[0])
            if entry.file_size > self.settings.max_zip_bytes:
                raise HTTPException(status_code=404, detail="Image not found.")
            return archive.read(entry)
