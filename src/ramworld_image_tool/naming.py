"""SEO-friendly output folder and filename rules."""

from enum import StrEnum
from pathlib import Path

from slugify import slugify


class ImageKind(StrEnum):
    """Image categories accepted by the application."""

    LOGO = "logo"
    COVER = "cover"
    GALLERY = "gallery"


class NamingLanguage(StrEnum):
    """Supported languages for generated filename labels."""

    ENGLISH = "english"
    ARABIC = "arabic"


FILENAME_PREFIXES = {
    NamingLanguage.ENGLISH: "ramworld",
    NamingLanguage.ARABIC: "عالم-رام",
}

IMAGE_KIND_LABELS = {
    NamingLanguage.ENGLISH: {
        ImageKind.LOGO: "logo",
        ImageKind.COVER: "cover",
        ImageKind.GALLERY: "gallery",
    },
    NamingLanguage.ARABIC: {
        ImageKind.LOGO: "شعار",
        ImageKind.COVER: "الغلاف",
        ImageKind.GALLERY: "صور",
    },
}


def filename_prefix(language: NamingLanguage = NamingLanguage.ENGLISH) -> str:
    """Return the brand prefix used by the selected naming language."""
    return FILENAME_PREFIXES[NamingLanguage(language)]


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
    *,
    language: NamingLanguage = NamingLanguage.ENGLISH,
    include_brand_prefix: bool = True,
) -> str:
    """Build a consistent SEO filename for an uploaded image."""
    normalized_extension = extension.lower().lstrip(".")
    if not normalized_extension:
        raise ValueError("An image extension is required.")

    selected_language = NamingLanguage(language)
    selected_labels = IMAGE_KIND_LABELS[selected_language]
    name_parts = [slugify_name(name), selected_labels[image_kind]]
    if include_brand_prefix:
        name_parts.insert(0, filename_prefix(selected_language))
    base_name = "-".join(name_parts)

    if image_kind is ImageKind.GALLERY:
        if gallery_index is None or gallery_index < 1:
            raise ValueError("Gallery images require an index starting at 1.")
        base_name = f"{base_name}-{gallery_index:02d}"
    elif gallery_index is not None:
        raise ValueError("Only gallery images can have an index.")

    return f"{base_name}.{normalized_extension}"
