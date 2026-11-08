"""Validated options shared by every image-tool integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .naming import FILENAME_PREFIXES, IMAGE_KIND_LABELS, ImageKind, NamingLanguage


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

DEFAULT_PREFIXES = FILENAME_PREFIXES
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
    include_brand_prefix: bool = True
    prefixes: Mapping[NamingLanguage, str] = field(default_factory=lambda: DEFAULT_PREFIXES.copy())
    labels: Mapping[NamingLanguage, Mapping[ImageKind, str]] = field(
        default_factory=lambda: {language: values.copy() for language, values in DEFAULT_LABELS.items()}
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
        for kind in ImageKind:
            if kind not in self.settings:
                raise ValueError(f"Missing optimization settings for {kind.value}.")
            if not isinstance(self.settings[kind], OptimizationSettings):
                raise ValueError(f"Invalid optimization settings for {kind.value}.")
            if self.target_formats.get(kind) not in {"original", "JPEG", "PNG", "WEBP"}:
                raise ValueError(f"Invalid target format for {kind.value}.")
        for selected_language in NamingLanguage:
            prefix = self.prefixes.get(selected_language)
            if not isinstance(prefix, str) or not prefix.strip():
                raise ValueError(f"Missing prefix for {selected_language.value}.")
            labels = self.labels.get(selected_language, {})
            if any(not isinstance(labels.get(kind), str) or not labels[kind].strip() for kind in ImageKind):
                raise ValueError(f"Missing image labels for {selected_language.value}.")
        object.__setattr__(self, "prefixes", MappingProxyType(dict(self.prefixes)))
        object.__setattr__(self, "labels", MappingProxyType({
            language: MappingProxyType(dict(values)) for language, values in self.labels.items()
        }))
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))
        object.__setattr__(self, "target_formats", MappingProxyType(dict(self.target_formats)))
