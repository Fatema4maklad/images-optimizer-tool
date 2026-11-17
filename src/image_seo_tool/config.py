"""Validated options shared by every image-tool integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .naming import IMAGE_KIND_LABELS, ImageKind, NamingLanguage, slugify_optional_prefix


@dataclass(frozen=True, slots=True)
class OptimizationSettings:
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

DEFAULT_LABELS = IMAGE_KIND_LABELS

DEFAULT_TARGET_FORMATS = {
    ImageKind.LOGO: "original",
    ImageKind.COVER: "WEBP",
    ImageKind.GALLERY: "WEBP",
}


@dataclass(frozen=True, slots=True)
class ToolConfig:
    """Processing policy. Pass one configuration to every adapter."""

    naming_language: NamingLanguage = NamingLanguage.ENGLISH
    filename_prefix: str = ""
    include_kind_label: bool = True
    max_pixels: int | None = None
    preserve_original_bytes: bool = True
    labels: Mapping[NamingLanguage, Mapping[ImageKind, str]] = field(
        default_factory=lambda: {
            language: values.copy() for language, values in DEFAULT_LABELS.items()
        }
    )
    settings: Mapping[ImageKind, OptimizationSettings] = field(
        default_factory=lambda: DEFAULT_SETTINGS.copy()
    )
    target_formats: Mapping[ImageKind, str] = field(
        default_factory=lambda: DEFAULT_TARGET_FORMATS.copy()
    )

    def __post_init__(self) -> None:
        language = NamingLanguage(self.naming_language)
        object.__setattr__(self, "naming_language", language)
        object.__setattr__(self, "filename_prefix", slugify_optional_prefix(self.filename_prefix))
        if not isinstance(self.include_kind_label, bool):
            raise ValueError("include_kind_label must be a boolean.")
        if self.max_pixels is not None and self.max_pixels < 1:
            raise ValueError("Maximum pixel count must be positive.")
        for kind in ImageKind:
            if kind not in self.settings:
                raise ValueError(f"Missing optimization settings for {kind.value}.")
            if not isinstance(self.settings[kind], OptimizationSettings):
                raise ValueError(f"Invalid optimization settings for {kind.value}.")
            if self.target_formats.get(kind) not in {"original", "JPEG", "PNG", "WEBP"}:
                raise ValueError(f"Invalid target format for {kind.value}.")
        for selected_language in NamingLanguage:
            labels = self.labels.get(selected_language, {})
            if any(
                not isinstance(labels.get(kind), str) or not labels[kind].strip()
                for kind in ImageKind
            ):
                raise ValueError(f"Missing image labels for {selected_language.value}.")
        object.__setattr__(self, "labels", MappingProxyType({
            language: MappingProxyType(dict(values)) for language, values in self.labels.items()
        }))
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))
        object.__setattr__(self, "target_formats", MappingProxyType(dict(self.target_formats)))
