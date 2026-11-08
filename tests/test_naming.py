from pathlib import Path

import pytest

from image_seo_tool.naming import (
    ImageKind,
    NamingLanguage,
    build_filename,
    create_output_folder,
    slugify_name,
)


def test_slugify_name() -> None:
    assert slugify_name("  Al Riyadh Company  ") == "al-riyadh-company"


def test_slugify_name_preserves_arabic() -> None:
    assert slugify_name("منتدى الرياض الاقتصادي") == "منتدى-الرياض-الاقتصادي"


def test_arabic_naming_language_uses_localized_type() -> None:
    assert (
        build_filename(
            "منتدى الرياض الاقتصادي",
            ImageKind.COVER,
            "webp",
            language=NamingLanguage.ARABIC,
        )
        == "منتدى-الرياض-الاقتصادي-الغلاف.webp"
    )


def test_arabic_gallery_filename_is_numbered() -> None:
    assert (
        build_filename(
            "منتدى الرياض الاقتصادي",
            ImageKind.GALLERY,
            "webp",
            2,
            language=NamingLanguage.ARABIC,
        )
        == "منتدى-الرياض-الاقتصادي-صور-02.webp"
    )


def test_arabic_logo_filename_uses_shiar_label() -> None:
    assert (
        build_filename(
            "شركة الرياض",
            ImageKind.LOGO,
            "png",
            language=NamingLanguage.ARABIC,
        )
        == "شركة-الرياض-شعار.png"
    )


def test_build_logo_filename() -> None:
    assert (
        build_filename("Al Riyadh Company", ImageKind.LOGO, ".PNG")
        == "al-riyadh-company-logo.png"
    )


def test_build_numbered_gallery_filename() -> None:
    assert (
        build_filename("Al Riyadh Company", ImageKind.GALLERY, "webp", 3)
        == "al-riyadh-company-gallery-03.webp"
    )


def test_build_filename_normalizes_custom_prefix() -> None:
    assert (
        build_filename(
            "Al Riyadh Company",
            ImageKind.GALLERY,
            "webp",
            3,
            prefix="My Brand",
        )
        == "my-brand-al-riyadh-company-gallery-03.webp"
    )


def test_arabic_filename_accepts_custom_prefix() -> None:
    assert (
        build_filename(
            "منتدى الرياض الاقتصادي",
            ImageKind.COVER,
            "webp",
            language=NamingLanguage.ARABIC,
            prefix="شركتي",
        )
        == "شركتي-منتدى-الرياض-الاقتصادي-الغلاف.webp"
    )


def test_gallery_requires_positive_index() -> None:
    with pytest.raises(ValueError, match="starting at 1"):
        build_filename("Al Riyadh Company", ImageKind.GALLERY, "webp", 0)


def test_create_one_output_folder(tmp_path: Path) -> None:
    result = create_output_folder(tmp_path, "Al Riyadh Company")

    assert result == tmp_path / "al-riyadh-company"
    assert result.is_dir()
