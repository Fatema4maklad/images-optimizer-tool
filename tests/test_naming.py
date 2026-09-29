from pathlib import Path

import pytest

from ramworld_image_tool.naming import (
    ImageKind,
    build_filename,
    create_output_folder,
    slugify_name,
)


def test_slugify_name() -> None:
    assert slugify_name("  Al Riyadh Company  ") == "al-riyadh-company"


def test_slugify_name_preserves_arabic() -> None:
    assert slugify_name("منتدى الرياض الاقتصادي") == "منتدى-الرياض-الاقتصادي"


def test_arabic_cover_filename() -> None:
    assert (
        build_filename("منتدى الرياض الاقتصادي", ImageKind.COVER, "jpg")
        == "ramworld-منتدى-الرياض-الاقتصادي-cover.jpg"
    )


def test_build_logo_filename() -> None:
    assert (
        build_filename("Al Riyadh Company", ImageKind.LOGO, ".PNG")
        == "ramworld-al-riyadh-company-logo.png"
    )


def test_build_numbered_gallery_filename() -> None:
    assert (
        build_filename("Al Riyadh Company", ImageKind.GALLERY, "jpg", 3)
        == "ramworld-al-riyadh-company-gallery-03.jpg"
    )


def test_gallery_requires_positive_index() -> None:
    with pytest.raises(ValueError, match="starting at 1"):
        build_filename("Al Riyadh Company", ImageKind.GALLERY, "jpg", 0)


def test_create_one_output_folder(tmp_path: Path) -> None:
    result = create_output_folder(tmp_path, "Al Riyadh Company")

    assert result == tmp_path / "al-riyadh-company"
    assert result.is_dir()
