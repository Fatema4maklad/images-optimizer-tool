from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from ramworld_image_tool import ImageKind
from ramworld_image_tool.batch import (
    UploadedImage,
    process_uploaded_images,
    suggest_alt_text,
)


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (1000, 500)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, "#1769aa").save(output, format=image_format)
    return output.getvalue()


def test_uploaded_batch_saves_one_folder_and_builds_zip(tmp_path: Path) -> None:
    result = process_uploaded_images(
        "Riyadh Tech Summit",
        tmp_path / "output",
        [
            UploadedImage("logo.png", image_bytes(), ImageKind.LOGO),
            UploadedImage("cover.jpg", image_bytes("JPEG"), ImageKind.COVER),
            UploadedImage(
                "gallery.jpg", image_bytes("JPEG"), ImageKind.GALLERY, 1
            ),
        ],
    )

    assert result.output_folder == tmp_path / "output" / "riyadh-tech-summit"
    assert all(image.output_path.parent == result.output_folder for image in result.images)
    with ZipFile(BytesIO(result.zip_data)) as archive:
        assert archive.namelist() == [
            "riyadh-tech-summit/ramworld-riyadh-tech-summit-cover.jpg",
            "riyadh-tech-summit/ramworld-riyadh-tech-summit-gallery-01.jpg",
            "riyadh-tech-summit/ramworld-riyadh-tech-summit-logo.png",
            "riyadh-tech-summit/ramworld-riyadh-tech-summit-image-seo.csv",
        ]


def test_collision_is_detected_before_new_files_are_written(tmp_path: Path) -> None:
    output_folder = tmp_path / "output" / "event"
    output_folder.mkdir(parents=True)
    existing_cover = output_folder / "ramworld-event-cover.jpg"
    existing_cover.write_bytes(b"existing")

    with pytest.raises(FileExistsError, match="already exist"):
        process_uploaded_images(
            "Event",
            tmp_path / "output",
            [
                UploadedImage("logo.png", image_bytes(), ImageKind.LOGO),
                UploadedImage("cover.jpg", image_bytes("JPEG"), ImageKind.COVER),
            ],
        )

    assert not (output_folder / "ramworld-event-logo.png").exists()
    assert existing_cover.read_bytes() == b"existing"


def test_invalid_batch_does_not_create_output_folder(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a valid"):
        process_uploaded_images(
            "Broken Event",
            tmp_path / "output",
            [UploadedImage("fake.png", b"not an image", ImageKind.LOGO)],
        )

    assert not (tmp_path / "output" / "broken-event").exists()


def test_arabic_batch_preserves_names_and_creates_localized_metadata(
    tmp_path: Path,
) -> None:
    event_name = "منتدى الرياض الاقتصادي"
    result = process_uploaded_images(
        event_name,
        tmp_path / "output",
        [
            UploadedImage(
                "cover.jpg",
                image_bytes("JPEG"),
                ImageKind.COVER,
                alt_text="غلاف منتدى الرياض الاقتصادي في الرياض",
            )
        ],
    )

    expected_filename = "ramworld-منتدى-الرياض-الاقتصادي-cover.jpg"
    assert result.output_folder.name == "منتدى-الرياض-الاقتصادي"
    assert result.images[0].output_path.name == expected_filename
    assert result.seo_metadata[0].alt_text == "غلاف منتدى الرياض الاقتصادي في الرياض"
    assert "%D9%85%D9%86%D8%AA%D8%AF%D9%89" in (
        result.seo_metadata[0].url_encoded_filename
    )
    metadata_text = result.metadata_csv.decode("utf-8-sig")
    assert expected_filename in metadata_text
    assert "غلاف منتدى الرياض الاقتصادي في الرياض" in metadata_text

    with ZipFile(BytesIO(result.zip_data)) as archive:
        assert (
            f"منتدى-الرياض-الاقتصادي/{expected_filename}" in archive.namelist()
        )


def test_alt_text_suggestions_follow_input_language() -> None:
    assert (
        suggest_alt_text("منتدى الرياض الاقتصادي", ImageKind.COVER)
        == "غلاف منتدى الرياض الاقتصادي"
    )
    assert (
        suggest_alt_text("Riyadh Economic Forum", ImageKind.LOGO)
        == "Riyadh Economic Forum logo"
    )
