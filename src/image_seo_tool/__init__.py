"""Reusable image optimization and SEO naming tools."""

from .version import __version__
from .batch import (
    BatchResult,
    SeoMetadata,
    UploadedImage,
    process_uploaded_images,
    save_processed_result,
    suggest_alt_text,
)
from .config import ToolConfig
from .core import ProcessedAsset, ProcessingResult, process_images
from .naming import (
    ImageKind,
    NamingLanguage,
    build_filename,
    create_output_folder,
    slugify_name,
    slugify_optional_prefix,
)
from .processor import (
    DEFAULT_SETTINGS,
    OptimizationSettings,
    ProcessedImage,
    optimize_image_bytes,
    process_image_file,
    process_image_set,
)

__all__ = [
    "__version__",
    "BatchResult",
    "ToolConfig",
    "ProcessedAsset",
    "ProcessingResult",
    "process_images",
    "SeoMetadata",
    "UploadedImage",
    "process_uploaded_images",
    "save_processed_result",
    "suggest_alt_text",
    "ImageKind",
    "NamingLanguage",
    "build_filename",
    "create_output_folder",
    "slugify_name",
    "slugify_optional_prefix",
    "DEFAULT_SETTINGS",
    "OptimizationSettings",
    "ProcessedImage",
    "optimize_image_bytes",
    "process_image_file",
    "process_image_set",
]
