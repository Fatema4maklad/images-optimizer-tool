"""RAM World image optimization tool."""

from .batch import (
    BatchResult,
    SeoMetadata,
    UploadedImage,
    process_uploaded_images,
    suggest_alt_text,
)
from .naming import ImageKind, build_filename, create_output_folder, slugify_name
from .processor import (
    DEFAULT_SETTINGS,
    OptimizationSettings,
    ProcessedImage,
    optimize_image_bytes,
    process_image_file,
    process_image_set,
)

__all__ = [
    "BatchResult",
    "SeoMetadata",
    "UploadedImage",
    "process_uploaded_images",
    "suggest_alt_text",
    "ImageKind",
    "build_filename",
    "create_output_folder",
    "slugify_name",
    "DEFAULT_SETTINGS",
    "OptimizationSettings",
    "ProcessedImage",
    "optimize_image_bytes",
    "process_image_file",
    "process_image_set",
]
