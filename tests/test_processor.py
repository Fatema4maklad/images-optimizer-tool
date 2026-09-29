from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from ramworld_image_tool.naming import ImageKind
from ramworld_image_tool.processor import (
    OptimizationSettings,
    optimize_image_bytes,
    process_image_set,
)


def make_image(path: Path, size: tuple[int, int], image_format: str = "PNG") -> None:
    Image.new("RGB", size, "#1769aa").save(path, format=image_format)


def test_cover_uses_event_name_and_is_resized() -> None:
    source = BytesIO()
    Image.new("RGB", (2400, 1600), "#1769aa").save(source, format="JPEG")

    filename, output, original_size, output_size = optimize_image_bytes(
        source.getvalue(),
        "Riyadh Tech Summit",
        ImageKind.COVER,
        settings=OptimizationSettings(1200, 600),
    )

    assert filename == "ramworld-riyadh-tech-summit-cover.jpg"
    assert original_size == (2400, 1600)
    assert output_size == (900, 600)
    assert output


def test_png_logo_keeps_transparency() -> None:
    source = BytesIO()
    Image.new("RGBA", (1600, 800), (23, 105, 170, 100)).save(source, format="PNG")

    _, output, _, output_size = optimize_image_bytes(
        source.getvalue(), "Partner Name", ImageKind.LOGO
    )

    with Image.open(BytesIO(output)) as result:
        assert "A" in result.getbands()
        assert output_size == (1200, 600)


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
        "ramworld-riyadh-tech-summit-logo.png",
        "ramworld-riyadh-tech-summit-cover.jpg",
        "ramworld-riyadh-tech-summit-gallery-01.jpg",
        "ramworld-riyadh-tech-summit-gallery-02.jpg",
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
