"""Image validation, resizing, optimization, and batch output handling."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import math
from pathlib import Path
import re
from typing import Sequence
from xml.etree import ElementTree

from PIL import Image, ImageOps, UnidentifiedImageError

from .config import DEFAULT_SETTINGS, OptimizationSettings, ToolConfig
from .naming import (
    ImageKind,
    NamingLanguage,
    build_filename,
    create_output_folder,
)


SUPPORTED_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "SVG": "svg",
}

SVG_LENGTH = re.compile(
    r"^\s*(?P<value>(?:\d+(?:\.\d*)?|\.\d+))\s*"
    r"(?P<unit>px|in|cm|mm|pt|pc)?\s*$",
    re.IGNORECASE,
)
SVG_UNIT_TO_PIXELS = {
    "": 1.0,
    "px": 1.0,
    "in": 96.0,
    "cm": 96.0 / 2.54,
    "mm": 96.0 / 25.4,
    "pt": 96.0 / 72.0,
    "pc": 16.0,
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


def _svg_root(image_data: bytes) -> ElementTree.Element | None:
    """Return the root for SVG data, or ``None`` for non-SVG input."""
    if b"\x00" in image_data:
        return None
    if b"<!DOCTYPE" in image_data.upper() or b"<!ENTITY" in image_data.upper():
        raise ValueError("SVG files containing DTDs or entities are not supported.")
    try:
        root = ElementTree.fromstring(image_data)
    except ElementTree.ParseError:
        return None
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        return None
    return root


def _svg_length(value: str | None) -> float | None:
    if not value:
        return None
    match = SVG_LENGTH.fullmatch(value)
    if match is None:
        return None
    length = float(match.group("value"))
    unit = match.group("unit") or ""
    return length * SVG_UNIT_TO_PIXELS[unit.lower()]


def _svg_dimensions(root: ElementTree.Element) -> tuple[int, int]:
    """Read an SVG's intrinsic pixel size, falling back to its viewBox."""
    width = _svg_length(root.get("width"))
    height = _svg_length(root.get("height"))
    viewbox_width: float | None = None
    viewbox_height: float | None = None
    viewbox = root.get("viewBox") or root.get("viewbox")
    if viewbox:
        try:
            _, _, viewbox_width, viewbox_height = (
                float(part) for part in re.split(r"[\s,]+", viewbox.strip())
            )
        except (TypeError, ValueError):
            raise ValueError("The SVG has an invalid viewBox.") from None

    if width is None and height is None:
        width, height = viewbox_width, viewbox_height
    elif width is None and height and viewbox_width and viewbox_height:
        width = height * viewbox_width / viewbox_height
    elif height is None and width and viewbox_width and viewbox_height:
        height = width * viewbox_height / viewbox_width

    if (
        not width
        or not height
        or not math.isfinite(width)
        or not math.isfinite(height)
        or width <= 0
        or height <= 0
    ):
        raise ValueError(
            "The SVG must define positive width and height values or a valid viewBox."
        )
    return max(1, round(width)), max(1, round(height))


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
    filename_prefix: str = "",
    config: ToolConfig | None = None,
) -> tuple[str, bytes, tuple[int, int], tuple[int, int]]:
    """Optimize image bytes and return its filename, bytes, and dimensions."""
    if not image_data:
        raise ValueError("The uploaded image is empty.")

    selected_config = config or ToolConfig(
        naming_language=naming_language, filename_prefix=filename_prefix
    )
    selected_settings = settings or selected_config.settings[image_kind]

    svg_root = _svg_root(image_data)
    if svg_root is not None:
        original_size = _svg_dimensions(svg_root)
        if selected_config.max_pixels is not None and math.prod(original_size) > selected_config.max_pixels:
            raise ValueError("The image exceeds the maximum pixel count.")
        filename = build_filename(
            entity_name,
            image_kind,
            SUPPORTED_FORMATS["SVG"],
            gallery_index,
            language=selected_config.naming_language,
            prefix=selected_config.filename_prefix,
            labels=selected_config.labels[selected_config.naming_language],
            include_kind_label=selected_config.include_kind_label,
        )
        return filename, image_data, original_size, original_size

    try:
        with Image.open(BytesIO(image_data)) as source:
            image_format = source.format
            if image_format not in SUPPORTED_FORMATS:
                supported = ", ".join(SUPPORTED_FORMATS.values())
                raise ValueError(f"Unsupported image format. Use {supported}.")
            if getattr(source, "is_animated", False):
                raise ValueError("Animated images are not supported.")

            original_size = source.size
            if selected_config.max_pixels is not None and math.prod(original_size) > selected_config.max_pixels:
                raise ValueError("The image exceeds the maximum pixel count.")
            configured_format = selected_config.target_formats[image_kind]
            target_format = image_format if configured_format == "original" else configured_format
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
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError("The uploaded file is not a valid supported image.") from exc

    was_resized = output_size != oriented_size
    was_rotated = exif_orientation != 1
    format_changed = target_format != image_format
    if (
        selected_config.preserve_original_bytes
        and not format_changed
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
        language=selected_config.naming_language,
        prefix=selected_config.filename_prefix,
        labels=selected_config.labels[selected_config.naming_language],
        include_kind_label=selected_config.include_kind_label,
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
    filename_prefix: str = "",
    overwrite: bool = False,
    config: ToolConfig | None = None,
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
        filename_prefix=filename_prefix,
        config=config,
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
    filename_prefix: str = "",
    overwrite: bool = False,
    config: ToolConfig | None = None,
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
                filename_prefix=filename_prefix,
                overwrite=overwrite,
                config=config,
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
                filename_prefix=filename_prefix,
                overwrite=overwrite,
                config=config,
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
                filename_prefix=filename_prefix,
                overwrite=overwrite,
                config=config,
            )
        )

    return results
