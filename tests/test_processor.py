from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from image_seo_tool.naming import ImageKind, NamingLanguage
from image_seo_tool.processor import (
    OptimizationSettings,
    optimize_image_bytes,
    process_image_set,
)


def make_image(path: Path, size: tuple[int, int], image_format: str = "PNG") -> None:
    Image.new("RGB", size, "#1769aa").save(path, format=image_format)


def svg_bytes(width: int = 800, height: int = 400) -> bytes:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="#1769aa"/></svg>'
    ).encode()


def test_cover_uses_event_name_and_is_resized() -> None:
    source = BytesIO()
    Image.new("RGB", (2400, 1600), "#1769aa").save(source, format="JPEG")

    filename, output, original_size, output_size = optimize_image_bytes(
        source.getvalue(),
        "Riyadh Tech Summit",
        ImageKind.COVER,
        settings=OptimizationSettings(1200, 600),
    )

    assert filename == "riyadh-tech-summit-cover.webp"
    assert original_size == (2400, 1600)
    assert output_size == (900, 600)
    with Image.open(BytesIO(output)) as result:
        assert result.format == "WEBP"


def test_png_logo_keeps_transparency() -> None:
    source = BytesIO()
    Image.new("RGBA", (1600, 800), (23, 105, 170, 100)).save(source, format="PNG")

    _, output, _, output_size = optimize_image_bytes(
        source.getvalue(), "Partner Name", ImageKind.LOGO
    )

    with Image.open(BytesIO(output)) as result:
        assert "A" in result.getbands()
        assert output_size == (1200, 600)


def test_svg_logo_stays_svg() -> None:
    source = svg_bytes()

    filename, output, original_size, output_size = optimize_image_bytes(
        source, "Partner Name", ImageKind.LOGO
    )

    assert filename == "partner-name-logo.svg"
    assert output == source
    assert original_size == (800, 400)
    assert output_size == original_size


def test_svg_cover_stays_svg() -> None:
    source = svg_bytes(2400, 1600)
    filename, output, original_size, output_size = optimize_image_bytes(
        source,
        "Riyadh Tech Summit",
        ImageKind.COVER,
        settings=OptimizationSettings(1200, 600),
    )

    assert filename == "riyadh-tech-summit-cover.svg"
    assert output == source
    assert original_size == (2400, 1600)
    assert output_size == original_size


def test_processor_uses_selected_arabic_naming_language() -> None:
    source = BytesIO()
    Image.new("RGB", (800, 400), "#1769aa").save(source, format="JPEG")

    filename, _, _, _ = optimize_image_bytes(
        source.getvalue(),
        "منتدى الرياض الاقتصادي",
        ImageKind.COVER,
        naming_language=NamingLanguage.ARABIC,
    )

    assert filename == "منتدى-الرياض-الاقتصادي-الغلاف.webp"


def test_image_set_uses_one_folder_and_numbers_gallery(tmp_path: Path) -> None:
    logo = tmp_path / "source-logo.png"
    cover = tmp_path / "source-cover.jpg"
    gallery_one = tmp_path / "gallery-one.jpg"
    gallery_two = tmp_path / "gallery-two.jpg"
    make_image(logo, (800, 400))
    make_image(cover, (2000, 1000), "JPEG")
    make_image(gallery_one, (1200, 900), "JPEG")
    make_image(gallery_two, (1200, 900), "JPEG")

    results = process_image_set(
        "Riyadh Tech Summit",
        tmp_path / "output",
        logo=logo,
        cover=cover,
        gallery=[gallery_one, gallery_two],
    )

    output_folders = {result.output_path.parent for result in results}
    assert output_folders == {tmp_path / "output" / "riyadh-tech-summit"}
    assert [result.output_path.name for result in results] == [
        "riyadh-tech-summit-logo.png",
        "riyadh-tech-summit-cover.webp",
        "riyadh-tech-summit-gallery-01.webp",
        "riyadh-tech-summit-gallery-02.webp",
    ]


def test_existing_output_is_not_overwritten(tmp_path: Path) -> None:
    logo = tmp_path / "logo.png"
    make_image(logo, (400, 200))
    process_image_set("Partner", tmp_path / "output", logo=logo)

    with pytest.raises(FileExistsError, match="already exists"):
        process_image_set("Partner", tmp_path / "output", logo=logo)


def test_rejects_non_image_data() -> None:
    with pytest.raises(ValueError, match="not a valid"):
        optimize_image_bytes(b"not an image", "Event", ImageKind.COVER)
