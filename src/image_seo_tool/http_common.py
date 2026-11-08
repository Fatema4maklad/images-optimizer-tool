"""Shared request parsing and response formatting for HTTP adapters."""

import json

from .api_models import ImageSummary
from .batch import BatchResult


def parse_gallery_alt_texts(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("Gallery alt text data is invalid.") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("Gallery alt text data is invalid.")
    return parsed


def summarize_images(result: BatchResult) -> list[ImageSummary]:
    metadata_by_name = {item.filename: item for item in result.seo_metadata}
    return [
        ImageSummary(
            filename=image.output_path.name,
            alt_text=metadata_by_name[image.output_path.name].alt_text,
            original_bytes=image.original_bytes,
            output_bytes=image.output_bytes,
            original_size=image.original_size,
            output_size=image.output_size,
            reduction_percent=image.reduction_percent,
        )
        for image in result.images
    ]
