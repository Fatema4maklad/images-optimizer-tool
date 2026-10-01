"""Image validation, resizing, optimization, and batch output handling."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageOps, UnidentifiedImageError

from .naming import (
    ImageKind,
    NamingLanguage,
    build_filename,
    create_output_folder,
)


SUPPORTED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


@dataclass(frozen=True, slots=True)
class OptimizationSettings:
    """Output limits and quality settings for one image category."""

    max_width: int
    max_height: int
    quality: int = 90

    def __post_init__(self) -> None:
        if self.max_width < 1 or self.max_height < 1:
            raise ValueError("Maximum image dimensions must be positive.")
        if not 1 <= self.quality <= 100:
            raise ValueError("Image quality must be between 1 and 100.")


DEFAULT_SETTINGS = {
    ImageKind.LOGO: OptimizationSettings(1200, 1200, 95),
    ImageKind.COVER: OptimizationSettings(1920, 1080, 88),
    ImageKind.GALLERY: OptimizationSettings(1920, 1920, 88),
}


@dataclass(frozen=True, slots=True)
class ProcessedImage:
    """Information shown to the user after an image is processed."""

    output_path: Path
    original_bytes: int
    output_bytes: int
    original_size: tuple[int, int]
    output_size: tuple[int, int]

    @property
    def bytes_saved(self) -> int:
        return max(0, self.original_bytes - self.output_bytes)

    @property
    def reduction_percent(self) -> float:
        if not self.original_bytes:
            return 0.0
        return self.bytes_saved / self.original_bytes * 100


def _encode_image(
    image: Image.Image,
    image_format: str,
    image_kind: ImageKind,
    quality: int,
    icc_profile: bytes | None,
) -> bytes:
    output = BytesIO()
    save_options: dict[str, object] = {}
    if icc_profile:
        save_options["icc_profile"] = icc_profile

    if image_format == "PNG":
        save_options.update(optimize=True, compress_level=9)
    elif image_format == "JPEG":
        if image.mode not in {"RGB", "L"}:
            if "A" in image.getbands():
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
        save_options.update(quality=quality, optimize=True, progressive=True)
    elif image_format == "WEBP":
        if image.mode not in {"RGB", "RGBA"}:
            has_transparency = (
                "A" in image.getbands() or "transparency" in image.info
            )
            image = image.convert("RGBA" if has_transparency else "RGB")
        save_options.update(
            quality=quality,
            method=6,
            lossless=image_kind is ImageKind.LOGO,
        )

    image.save(output, format=image_format, **save_options)
    return output.getvalue()


def optimize_image_bytes(
    image_data: bytes,
    entity_name: str,
    image_kind: ImageKind,
    *,
    gallery_index: int | None = None,
    settings: OptimizationSettings | None = None,
    naming_language: NamingLanguage = NamingLanguage.ENGLISH,
) -> tuple[str, bytes, tuple[int, int], tuple[int, int]]:
    """Optimize image bytes and return its filename, bytes, and dimensions."""
    if not image_data:
        raise ValueError("The uploaded image is empty.")

    selected_settings = settings or DEFAULT_SETTINGS[image_kind]

    try:
        with Image.open(BytesIO(image_data)) as source:
            image_format = source.format
            if image_format not in SUPPORTED_FORMATS:
                supported = ", ".join(SUPPORTED_FORMATS.values())
                raise ValueError(f"Unsupported image format. Use {supported}.")
            if getattr(source, "is_animated", False):
                raise ValueError("Animated images are not supported.")

            original_size = source.size
            target_format = (
                image_format if image_kind is ImageKind.LOGO else "WEBP"
            )
            exif_orientation = source.getexif().get(274, 1)
            icc_profile = source.info.get("icc_profile")
            optimized = ImageOps.exif_transpose(source)
            oriented_size = optimized.size
            optimized.thumbnail(
                (selected_settings.max_width, selected_settings.max_height),
                Image.Resampling.LANCZOS,
            )
            output_size = optimized.size
            encoded = _encode_image(
                optimized,
                target_format,
                image_kind,
                selected_settings.quality,
                icc_profile,
            )
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The uploaded file is not a valid supported image.") from exc

    was_resized = output_size != oriented_size
    was_rotated = exif_orientation != 1
    format_changed = target_format != image_format
    if (
        not format_changed
        and not was_resized
        and not was_rotated
        and len(encoded) >= len(image_data)
    ):
        encoded = image_data

    filename = build_filename(
        entity_name,
        image_kind,
        SUPPORTED_FORMATS[target_format],
        gallery_index,
        language=naming_language,
    )
    return filename, encoded, original_size, output_size


def process_image_file(
    input_path: Path,
    output_folder: Path,
    entity_name: str,
    image_kind: ImageKind,
    *,
    gallery_index: int | None = None,
    settings: OptimizationSettings | None = None,
    naming_language: NamingLanguage = NamingLanguage.ENGLISH,
    overwrite: bool = False,
) -> ProcessedImage:
    """Process one image and write it into an existing entity folder."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"Image not found: {input_path}")

    image_data = input_path.read_bytes()
    filename, output_data, original_size, output_size = optimize_image_bytes(
        image_data,
        entity_name,
        image_kind,
        gallery_index=gallery_index,
        settings=settings,
        naming_language=naming_language,
    )

    output_path = Path(output_folder) / filename
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Output image already exists: {output_path.name}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output_data)
    return ProcessedImage(
        output_path=output_path,
        original_bytes=len(image_data),
        output_bytes=len(output_data),
        original_size=original_size,
        output_size=output_size,
    )


def process_image_set(
    entity_name: str,
    output_root: Path,
    *,
    logo: Path | None = None,
    cover: Path | None = None,
    gallery: Sequence[Path] = (),
    naming_language: NamingLanguage = NamingLanguage.ENGLISH,
    overwrite: bool = False,
) -> list[ProcessedImage]:
    """Process all supplied images into one folder for an event or organization."""
    if logo is None and cover is None and not gallery:
        raise ValueError("At least one image is required.")

    output_folder = create_output_folder(Path(output_root), entity_name)
    results: list[ProcessedImage] = []

    if logo is not None:
        results.append(
            process_image_file(
                logo,
                output_folder,
                entity_name,
                ImageKind.LOGO,
                naming_language=naming_language,
                overwrite=overwrite,
            )
        )
    if cover is not None:
        results.append(
            process_image_file(
                cover,
                output_folder,
                entity_name,
                ImageKind.COVER,
                naming_language=naming_language,
                overwrite=overwrite,
            )
        )
    for index, gallery_image in enumerate(gallery, start=1):
        results.append(
            process_image_file(
                gallery_image,
                output_folder,
                entity_name,
                ImageKind.GALLERY,
                gallery_index=index,
                naming_language=naming_language,
                overwrite=overwrite,
            )
        )

    return results
