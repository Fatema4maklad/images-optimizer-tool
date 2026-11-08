"""Storage-independent image processing and publishing metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from urllib.parse import quote

from .config import ToolConfig
from .naming import ImageKind, NamingLanguage, slugify_name
from .processor import optimize_image_bytes


MIME_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "svg": "image/svg+xml"}
ARABIC_CHARACTER = re.compile(r"[\u0600-\u06ff]")


@dataclass(frozen=True, slots=True)
class UploadedImage:
    original_name: str
    data: bytes
    image_kind: ImageKind
    gallery_index: int | None = None
    alt_text: str | None = None


@dataclass(frozen=True, slots=True)
class SeoMetadata:
    image_kind: ImageKind
    filename: str
    alt_text: str
    url_encoded_filename: str
    html_example: str


@dataclass(frozen=True, slots=True)
class ProcessedAsset:
    """One complete output that a caller may store anywhere."""

    filename: str
    data: bytes
    mime_type: str
    image_kind: ImageKind
    alt_text: str
    original_name: str
    original_bytes: int
    original_size: tuple[int, int]
    output_size: tuple[int, int]

    @property
    def output_bytes(self) -> int:
        return len(self.data)

    @property
    def reduction_percent(self) -> float:
        if not self.original_bytes:
            return 0.0
        return max(0, self.original_bytes - self.output_bytes) / self.original_bytes * 100


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Portable result with no filesystem or web-server dependency."""

    slug: str
    assets: tuple[ProcessedAsset, ...]
    seo_metadata: tuple[SeoMetadata, ...]

    @property
    def original_bytes(self) -> int:
        return sum(asset.original_bytes for asset in self.assets)

    @property
    def output_bytes(self) -> int:
        return sum(asset.output_bytes for asset in self.assets)

    @property
    def reduction_percent(self) -> float:
        if not self.original_bytes:
            return 0.0
        return max(0, self.original_bytes - self.output_bytes) / self.original_bytes * 100


def suggest_alt_text(
    entity_name: str,
    image_kind: ImageKind,
    gallery_index: int | None = None,
    language: NamingLanguage | None = None,
) -> str:
    clean_name = " ".join(entity_name.split())
    if not clean_name:
        raise ValueError("A company, event, or partner name is required.")
    selected_language = language or (
        NamingLanguage.ARABIC if ARABIC_CHARACTER.search(clean_name) else NamingLanguage.ENGLISH
    )
    if selected_language is NamingLanguage.ARABIC:
        if image_kind is ImageKind.LOGO:
            return f"شعار {clean_name}"
        if image_kind is ImageKind.COVER:
            return f"غلاف {clean_name}"
        return f"صورة {gallery_index or 1} من {clean_name}"
    if image_kind is ImageKind.LOGO:
        return f"{clean_name} logo"
    if image_kind is ImageKind.COVER:
        return f"{clean_name} cover"
    return f"{clean_name} gallery photo {gallery_index or 1}"


def make_seo_metadata(image_kind: ImageKind, filename: str, alt_text: str) -> SeoMetadata:
    encoded_filename = quote(filename)
    return SeoMetadata(
        image_kind=image_kind,
        filename=filename,
        alt_text=alt_text,
        url_encoded_filename=encoded_filename,
        html_example=f'<img src="{encoded_filename}" alt="{escape(alt_text, quote=True)}">',
    )


def process_images(
    entity_name: str,
    uploads: list[UploadedImage],
    *,
    config: ToolConfig | None = None,
) -> ProcessingResult:
    """Process uploads without saving files or creating a ZIP."""
    if not uploads:
        raise ValueError("Upload at least one image.")
    selected_config = config or ToolConfig()
    slug = slugify_name(entity_name)
    assets: list[ProcessedAsset] = []
    metadata: list[SeoMetadata] = []
    for upload in uploads:
        filename, data, original_size, output_size = optimize_image_bytes(
            upload.data,
            entity_name,
            upload.image_kind,
            gallery_index=upload.gallery_index,
            config=selected_config,
        )
        alt_text = (
            upload.alt_text.strip()
            if upload.alt_text is not None
            else suggest_alt_text(
                entity_name, upload.image_kind, upload.gallery_index, selected_config.naming_language
            )
        )
        assets.append(
            ProcessedAsset(
                filename=filename,
                data=data,
                mime_type=MIME_TYPES[filename.rsplit(".", 1)[1]],
                image_kind=upload.image_kind,
                alt_text=alt_text,
                original_name=upload.original_name,
                original_bytes=len(upload.data),
                original_size=original_size,
                output_size=output_size,
            )
        )
        metadata.append(make_seo_metadata(upload.image_kind, filename, alt_text))
    filenames = [asset.filename for asset in assets]
    if len(filenames) != len(set(filenames)):
        raise ValueError("The upload contains duplicate output filenames.")
    return ProcessingResult(slug=slug, assets=tuple(assets), seo_metadata=tuple(metadata))
