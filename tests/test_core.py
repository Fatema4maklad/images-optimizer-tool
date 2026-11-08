from dataclasses import replace
from io import BytesIO

import pytest
from PIL import Image

from image_seo_tool import (
    ImageKind,
    OptimizationSettings,
    ToolConfig,
    UploadedImage,
    process_images,
    process_uploaded_images,
)


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1600, 800), "#1769aa").save(output, format="JPEG")
    return output.getvalue()


def test_portable_result_and_local_adapter_use_same_output(tmp_path) -> None:
    uploads = [UploadedImage("source.jpg", image_bytes(), ImageKind.COVER)]
    portable = process_images("Example Event", uploads)
    local = process_uploaded_images("Example Event", tmp_path, uploads)

    asset = portable.assets[0]
    assert asset.filename == local.images[0].output_path.name
    assert asset.data == local.images[0].output_path.read_bytes()
    assert asset.mime_type == "image/webp"
    assert asset.alt_text == local.seo_metadata[0].alt_text
    assert asset.output_size == local.images[0].output_size
    assert portable.output_bytes == local.output_bytes


def test_config_customizes_naming_dimensions_and_format(tmp_path) -> None:
    defaults = ToolConfig()
    config = replace(
        defaults,
        filename_prefix="Partner Team",
        settings={**defaults.settings, ImageKind.COVER: OptimizationSettings(800, 800, 80)},
        target_formats={**defaults.target_formats, ImageKind.COVER: "JPEG"},
    )
    uploads = [UploadedImage("source.jpg", image_bytes(), ImageKind.COVER)]
    portable = process_images("Example Event", uploads, config=config)
    local = process_uploaded_images("Example Event", tmp_path, uploads, config=config)

    assert portable.assets[0].filename == "partner-team-example-event-cover.jpg"
    assert portable.assets[0].mime_type == "image/jpeg"
    assert portable.assets[0].output_size == (800, 400)
    assert local.images[0].output_path.read_bytes() == portable.assets[0].data
    assert local.metadata_path.name == "example-event-image-seo.csv"


def test_config_is_validated_and_copies_input_mappings() -> None:
    formats = {**ToolConfig().target_formats, ImageKind.COVER: "TIFF"}
    with pytest.raises(ValueError, match="Invalid target format"):
        ToolConfig(target_formats=formats)

    with pytest.raises(ValueError, match="Prefix must contain"):
        ToolConfig(filename_prefix="!!!")

    labels = {language: dict(values) for language, values in ToolConfig().labels.items()}
    config = ToolConfig(labels=labels)
    labels[config.naming_language][ImageKind.COVER] = "changed"
    assert config.labels[config.naming_language][ImageKind.COVER] == "cover"
