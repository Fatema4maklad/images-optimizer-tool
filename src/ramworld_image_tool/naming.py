"""SEO-friendly output folder and filename rules."""

from enum import StrEnum
from pathlib import Path

from slugify import slugify


class ImageKind(StrEnum):
    """Image categories accepted by the application."""

    LOGO = "logo"
    COVER = "cover"
    GALLERY = "gallery"


def slugify_name(name: str) -> str:
    """Convert an event, company, or partner name into a safe URL-style slug."""
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("A company, event, or partner name is required.")

    # Keep localized words readable for the target audience. Latin text is
    # still normalized to lowercase, while Arabic remains Arabic.
    slug = slugify(cleaned_name, lowercase=True, allow_unicode=True)
    if not slug:
        raise ValueError("The name must contain letters or numbers.")
    return slug


def create_output_folder(output_root: Path, name: str) -> Path:
    """Create and return the single output folder used for one named entity."""
    output_folder = output_root / slugify_name(name)
    output_folder.mkdir(parents=True, exist_ok=True)
    return output_folder


def build_filename(
    name: str,
    image_kind: ImageKind,
    extension: str,
    gallery_index: int | None = None,
) -> str:
    """Build a consistent SEO filename for an uploaded image."""
    normalized_extension = extension.lower().lstrip(".")
    if not normalized_extension:
        raise ValueError("An image extension is required.")

    base_name = f"ramworld-{slugify_name(name)}-{image_kind.value}"

    if image_kind is ImageKind.GALLERY:
        if gallery_index is None or gallery_index < 1:
            raise ValueError("Gallery images require an index starting at 1.")
        base_name = f"{base_name}-{gallery_index:02d}"
    elif gallery_index is not None:
        raise ValueError("Only gallery images can have an index.")

    return f"{base_name}.{normalized_extension}"
