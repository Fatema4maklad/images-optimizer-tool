"""In-memory batch processing used by the web interface."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from html import escape
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from .naming import (
    ImageKind,
    NamingLanguage,
    filename_prefix,
    slugify_name,
)
from .processor import ProcessedImage, optimize_image_bytes


@dataclass(frozen=True, slots=True)
class UploadedImage:
    """One image received from the web interface."""

    original_name: str
    data: bytes
    image_kind: ImageKind
    gallery_index: int | None = None
    alt_text: str | None = None


@dataclass(frozen=True, slots=True)
class SeoMetadata:
    """Publishing information for one optimized image."""

    image_kind: ImageKind
    filename: str
    alt_text: str
    url_encoded_filename: str
    html_example: str


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Files and summary information produced by one processing run."""

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
        saved = max(0, self.original_bytes - self.output_bytes)
        return saved / self.original_bytes * 100


@dataclass(frozen=True, slots=True)
class _PreparedImage:
    filename: str
    data: bytes
    original_bytes: int
    original_size: tuple[int, int]
    output_size: tuple[int, int]
    image_kind: ImageKind
    alt_text: str


ARABIC_CHARACTER = re.compile(r"[\u0600-\u06ff]")
METADATA_COLUMNS = (
    "image_type",
    "filename",
    "alt_text",
    "url_encoded_filename",
    "html_example",
)


def suggest_alt_text(
    entity_name: str,
    image_kind: ImageKind,
    gallery_index: int | None = None,
    language: NamingLanguage | None = None,
) -> str:
    """Create a concise localized starting point for HTML alt text."""
    clean_name = " ".join(entity_name.split())
    if not clean_name:
        raise ValueError("A company, event, or partner name is required.")

    selected_language = language
    if selected_language is None:
        selected_language = (
            NamingLanguage.ARABIC
            if ARABIC_CHARACTER.search(clean_name)
            else NamingLanguage.ENGLISH
        )

    if selected_language is NamingLanguage.ARABIC:
        if image_kind is ImageKind.LOGO:
            return f"شعار {clean_name}"
        if image_kind is ImageKind.COVER:
            return f"غلاف {clean_name}"
        index = gallery_index or 1
        return f"صورة {index} من {clean_name}"

    if image_kind is ImageKind.LOGO:
        return f"{clean_name} logo"
    if image_kind is ImageKind.COVER:
        return f"{clean_name} cover"
    index = gallery_index or 1
    return f"{clean_name} gallery photo {index}"


def _make_seo_metadata(
    image_kind: ImageKind,
    filename: str,
    alt_text: str,
) -> SeoMetadata:
    encoded_filename = quote(filename)
    html_example = (
        f'<img src="{encoded_filename}" alt="{escape(alt_text, quote=True)}">'
    )
    return SeoMetadata(
        image_kind=image_kind,
        filename=filename,
        alt_text=alt_text,
        url_encoded_filename=encoded_filename,
        html_example=html_example,
    )


def _metadata_to_csv(entries: tuple[SeoMetadata, ...]) -> bytes:
    text_output = StringIO(newline="")
    writer = csv.DictWriter(text_output, fieldnames=METADATA_COLUMNS)
    writer.writeheader()
    for entry in entries:
        writer.writerow(
            {
                "image_type": entry.image_kind.value,
                "filename": entry.filename,
                "alt_text": entry.alt_text,
                "url_encoded_filename": entry.url_encoded_filename,
                "html_example": entry.html_example,
            }
        )
    return text_output.getvalue().encode("utf-8-sig")


def _read_metadata(metadata_path: Path) -> list[SeoMetadata]:
    if not metadata_path.is_file():
        return []
    try:
        rows = csv.DictReader(
            StringIO(metadata_path.read_text(encoding="utf-8-sig"))
        )
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
) -> BatchResult:
    """Validate, optimize, save, and package a set of uploaded images."""
    if not uploads:
        raise ValueError("Upload at least one image.")

    slug = slugify_name(entity_name)
    output_folder = Path(output_root) / slug
    prepared: list[_PreparedImage] = []

    # Prepare every image before writing anything, so invalid batches leave no
    # half-finished event folder behind.
    for upload in uploads:
        filename, output_data, original_size, output_size = optimize_image_bytes(
            upload.data,
            entity_name,
            upload.image_kind,
            gallery_index=upload.gallery_index,
            naming_language=naming_language,
            include_brand_prefix=include_brand_prefix,
        )
        prepared.append(
            _PreparedImage(
                filename=filename,
                data=output_data,
                original_bytes=len(upload.data),
                original_size=original_size,
                output_size=output_size,
                image_kind=upload.image_kind,
                alt_text=(
                    upload.alt_text.strip()
                    if upload.alt_text is not None
                    else suggest_alt_text(
                        entity_name,
                        upload.image_kind,
                        upload.gallery_index,
                        naming_language,
                    )
                ),
            )
        )

    filenames = [image.filename for image in prepared]
    if len(filenames) != len(set(filenames)):
        raise ValueError("The upload contains duplicate output filenames.")

    collisions = [
        image.filename
        for image in prepared
        if (output_folder / image.filename).exists()
    ]
    if collisions and not overwrite:
        joined_names = ", ".join(collisions)
        raise FileExistsError(
            f"These files already exist: {joined_names}. Enable replacement to continue."
        )

    output_folder.mkdir(parents=True, exist_ok=True)
    results: list[ProcessedImage] = []
    new_metadata: list[SeoMetadata] = []
    for image in prepared:
        output_path = output_folder / image.filename
        output_path.write_bytes(image.data)
        results.append(
            ProcessedImage(
                output_path=output_path,
                original_bytes=image.original_bytes,
                output_bytes=len(image.data),
                original_size=image.original_size,
                output_size=image.output_size,
            )
        )
        new_metadata.append(
            _make_seo_metadata(image.image_kind, image.filename, image.alt_text)
        )

    metadata_base = (
        f"{filename_prefix(naming_language)}-{slug}"
        if include_brand_prefix
        else slug
    )
    metadata_path = output_folder / f"{metadata_base}-image-seo.csv"
    metadata_by_filename = {
        entry.filename: entry for entry in _read_metadata(metadata_path)
    }
    metadata_by_filename.update(
        {entry.filename: entry for entry in new_metadata}
    )
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".svg"}
    saved_images = sorted(
        path
        for path in output_folder.iterdir()
        if path.is_file() and path.suffix.lower() in image_extensions
    )
    saved_filenames = {path.name for path in saved_images}
    metadata_by_filename = {
        filename: entry
        for filename, entry in metadata_by_filename.items()
        if filename in saved_filenames
    }
    kind_order = {
        ImageKind.LOGO: 0,
        ImageKind.COVER: 1,
        ImageKind.GALLERY: 2,
    }
    seo_metadata = tuple(
        sorted(
            metadata_by_filename.values(),
            key=lambda entry: (kind_order[entry.image_kind], entry.filename),
        )
    )
    metadata_csv = _metadata_to_csv(seo_metadata)
    metadata_path.write_bytes(metadata_csv)

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w", compression=ZIP_DEFLATED) as archive:
        for image_path in saved_images:
            archive.write(image_path, f"{slug}/{image_path.name}")
        archive.writestr(f"{slug}/{metadata_path.name}", metadata_csv)

    return BatchResult(
        output_folder=output_folder,
        images=tuple(results),
        seo_metadata=seo_metadata,
        metadata_path=metadata_path,
        metadata_csv=metadata_csv,
        zip_data=zip_buffer.getvalue(),
    )
