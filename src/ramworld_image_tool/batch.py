"""Local-filesystem and ZIP adapter for the portable processing core."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .config import ToolConfig
from .core import SeoMetadata, UploadedImage, process_images, suggest_alt_text
from .naming import ImageKind, NamingLanguage
from .processor import ProcessedImage


METADATA_COLUMNS = (
    "image_type", "filename", "alt_text", "url_encoded_filename", "html_example"
)


@dataclass(frozen=True, slots=True)
class BatchResult:
    output_folder: Path
    images: tuple[ProcessedImage, ...]
    seo_metadata: tuple[SeoMetadata, ...]
    metadata_path: Path
    metadata_csv: bytes
    zip_data: bytes

    @property
    def original_bytes(self) -> int:
        return sum(image.original_bytes for image in self.images)

    @property
    def output_bytes(self) -> int:
        return sum(image.output_bytes for image in self.images)

    @property
    def reduction_percent(self) -> float:
        if not self.original_bytes:
            return 0.0
        return max(0, self.original_bytes - self.output_bytes) / self.original_bytes * 100


def _metadata_to_csv(entries: tuple[SeoMetadata, ...]) -> bytes:
    text_output = StringIO(newline="")
    writer = csv.DictWriter(text_output, fieldnames=METADATA_COLUMNS)
    writer.writeheader()
    for entry in entries:
        writer.writerow({
            "image_type": entry.image_kind.value,
            "filename": entry.filename,
            "alt_text": entry.alt_text,
            "url_encoded_filename": entry.url_encoded_filename,
            "html_example": entry.html_example,
        })
    return text_output.getvalue().encode("utf-8-sig")


def _read_metadata(metadata_path: Path) -> list[SeoMetadata]:
    if not metadata_path.is_file():
        return []
    try:
        rows = csv.DictReader(StringIO(metadata_path.read_text(encoding="utf-8-sig")))
        return [
            SeoMetadata(
                image_kind=ImageKind(row["image_type"]),
                filename=row["filename"],
                alt_text=row["alt_text"],
                url_encoded_filename=row["url_encoded_filename"],
                html_example=row["html_example"],
            )
            for row in rows
        ]
    except (KeyError, ValueError, UnicodeError):
        return []


def process_uploaded_images(
    entity_name: str,
    output_root: Path,
    uploads: list[UploadedImage],
    *,
    naming_language: NamingLanguage = NamingLanguage.ENGLISH,
    include_brand_prefix: bool = True,
    overwrite: bool = False,
    config: ToolConfig | None = None,
) -> BatchResult:
    """Save a core result locally, merge SEO metadata, and prepare a ZIP."""
    selected_config = config or ToolConfig(
        naming_language=naming_language, include_brand_prefix=include_brand_prefix
    )
    processed = process_images(entity_name, uploads, config=selected_config)
    output_folder = Path(output_root) / processed.slug
    collisions = [
        asset.filename for asset in processed.assets
        if (output_folder / asset.filename).exists()
    ]
    if collisions and not overwrite:
        raise FileExistsError(
            f"These files already exist: {', '.join(collisions)}. Enable replacement to continue."
        )

    output_folder.mkdir(parents=True, exist_ok=True)
    results: list[ProcessedImage] = []
    for asset in processed.assets:
        output_path = output_folder / asset.filename
        output_path.write_bytes(asset.data)
        results.append(ProcessedImage(
            output_path=output_path,
            original_bytes=asset.original_bytes,
            output_bytes=asset.output_bytes,
            original_size=asset.original_size,
            output_size=asset.output_size,
        ))

    metadata_base = (
        f"{selected_config.prefixes[selected_config.naming_language]}-{processed.slug}"
        if selected_config.include_brand_prefix else processed.slug
    )
    metadata_path = output_folder / f"{metadata_base}-image-seo.csv"
    metadata_by_filename = {
        entry.filename: entry for entry in _read_metadata(metadata_path)
    }
    metadata_by_filename.update({
        entry.filename: entry for entry in processed.seo_metadata
    })
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".svg"}
    saved_images = sorted(
        path for path in output_folder.iterdir()
        if path.is_file() and path.suffix.lower() in image_extensions
    )
    saved_filenames = {path.name for path in saved_images}
    kind_order = {ImageKind.LOGO: 0, ImageKind.COVER: 1, ImageKind.GALLERY: 2}
    seo_metadata = tuple(sorted(
        (entry for filename, entry in metadata_by_filename.items() if filename in saved_filenames),
        key=lambda entry: (kind_order[entry.image_kind], entry.filename),
    ))
    metadata_csv = _metadata_to_csv(seo_metadata)
    metadata_path.write_bytes(metadata_csv)

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w", compression=ZIP_DEFLATED) as archive:
        for image_path in saved_images:
            archive.write(image_path, f"{processed.slug}/{image_path.name}")
        archive.writestr(f"{processed.slug}/{metadata_path.name}", metadata_csv)

    return BatchResult(
        output_folder=output_folder,
        images=tuple(results),
        seo_metadata=seo_metadata,
        metadata_path=metadata_path,
        metadata_csv=metadata_csv,
        zip_data=zip_buffer.getvalue(),
    )
