from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from image_seo_tool import ImageKind, NamingLanguage
from image_seo_tool.batch import (
    UploadedImage,
    process_uploaded_images,
    suggest_alt_text,
)


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (1000, 500)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, "#1769aa").save(output, format=image_format)
    return output.getvalue()


def svg_bytes() -> bytes:
    return (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">'
        b'<rect width="800" height="400" fill="#1769aa"/></svg>'
    )


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
            "riyadh-tech-summit/riyadh-tech-summit-cover.webp",
            "riyadh-tech-summit/riyadh-tech-summit-gallery-01.webp",
            "riyadh-tech-summit/riyadh-tech-summit-logo.png",
            "riyadh-tech-summit/riyadh-tech-summit-image-seo.csv",
        ]


def test_blank_prefix_does_not_add_a_brand_to_names(tmp_path: Path) -> None:
    result = process_uploaded_images(
        "Testing",
        tmp_path,
        [UploadedImage("logo.png", image_bytes(), ImageKind.LOGO)],
        filename_prefix="",
    )

    assert result.output_folder.name == "testing"
    assert [image.output_path.name for image in result.images] == ["testing-logo.png"]
    assert result.metadata_path.name == "testing-image-seo.csv"
    with ZipFile(BytesIO(result.zip_data)) as archive:
        assert archive.namelist() == [
            "testing/testing-logo.png",
            "testing/testing-image-seo.csv",
        ]


def test_uploaded_svg_logo_is_included_in_zip(tmp_path: Path) -> None:
    result = process_uploaded_images(
        "SVG Partner",
        tmp_path / "output",
        [UploadedImage("logo.svg", svg_bytes(), ImageKind.LOGO)],
    )

    assert result.images[0].output_path.name == "svg-partner-logo.svg"
    with ZipFile(BytesIO(result.zip_data)) as archive:
        assert "svg-partner/svg-partner-logo.svg" in archive.namelist()


def test_collision_is_detected_before_new_files_are_written(tmp_path: Path) -> None:
    output_folder = tmp_path / "output" / "event"
    output_folder.mkdir(parents=True)
    existing_cover = output_folder / "event-cover.webp"
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

    assert not (output_folder / "event-logo.png").exists()
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
        naming_language=NamingLanguage.ARABIC,
    )

    expected_filename = "منتدى-الرياض-الاقتصادي-الغلاف.webp"
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
        assert (
            "منتدى-الرياض-الاقتصادي/"
            "منتدى-الرياض-الاقتصادي-image-seo.csv"
            in archive.namelist()
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
    assert (
        suggest_alt_text(
            "Riyadh Economic Forum",
            ImageKind.LOGO,
            language=NamingLanguage.ARABIC,
        )
        == "شعار Riyadh Economic Forum"
    )


def test_one_metadata_csv_covers_images_with_different_prefixes(tmp_path: Path) -> None:
    first = process_uploaded_images(
        "Event",
        tmp_path,
        [UploadedImage("cover.jpg", image_bytes("JPEG"), ImageKind.COVER)],
        filename_prefix="Client Brand",
    )
    second = process_uploaded_images(
        "Event",
        tmp_path,
        [UploadedImage("logo.png", image_bytes(), ImageKind.LOGO)],
    )

    assert first.metadata_path == second.metadata_path
    assert first.metadata_path.name == "event-image-seo.csv"
    assert {entry.filename for entry in second.seo_metadata} == {
        "client-brand-event-cover.webp", "event-logo.png"
    }
    with ZipFile(BytesIO(second.zip_data)) as archive:
        assert "event/client-brand-event-cover.webp" in archive.namelist()
        assert "event/event-logo.png" in archive.namelist()


def test_zip_only_includes_images_tracked_by_project_metadata(tmp_path: Path) -> None:
    output_folder = tmp_path / "event"
    output_folder.mkdir()
    (output_folder / "old-brand-event-cover.webp").write_bytes(b"older file")

    result = process_uploaded_images(
        "Event",
        tmp_path,
        [UploadedImage("logo.png", image_bytes(), ImageKind.LOGO)],
    )

    with ZipFile(BytesIO(result.zip_data)) as archive:
        assert "event/event-logo.png" in archive.namelist()
        assert "event/old-brand-event-cover.webp" not in archive.namelist()


def test_blank_optional_alt_text_is_not_regenerated(tmp_path: Path) -> None:
    result = process_uploaded_images(
        "Event",
        tmp_path / "output",
        [
            UploadedImage(
                "logo.png",
                image_bytes(),
                ImageKind.LOGO,
                alt_text="   ",
            )
        ],
    )

    assert result.seo_metadata[0].alt_text == ""
    assert 'alt=""' in result.seo_metadata[0].html_example
