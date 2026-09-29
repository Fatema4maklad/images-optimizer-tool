"""Streamlit interface for the RAM World image optimization tool."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ramworld_image_tool import (
    BatchResult,
    ImageKind,
    UploadedImage,
    process_uploaded_images,
    slugify_name,
    suggest_alt_text,
)


APP_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = APP_ROOT / "output"
ACCEPTED_IMAGE_TYPES = ["png", "jpg", "jpeg", "webp"]


def clear_last_result() -> None:
    """Hide stale results whenever the form inputs change."""
    st.session_state.pop("last_result", None)
    st.session_state.pop("last_slug", None)


def reset_after_source_change() -> None:
    """Clear generated suggestions when a name or selected file changes."""
    clear_last_result()
    for key in list(st.session_state):
        if key.startswith("alt_text_"):
            del st.session_state[key]


def clear_uploader(upload_type: str) -> None:
    """Replace one uploader widget with a fresh, empty instance."""
    reset_after_source_change()
    version_key = f"{upload_type}_uploader_version"
    st.session_state[version_key] = st.session_state.get(version_key, 0) + 1


def clear_all_uploaders() -> None:
    """Empty the logo, cover, and gallery uploaders together."""
    reset_after_source_change()
    for upload_type in ("logo", "cover", "gallery"):
        version_key = f"{upload_type}_uploader_version"
        st.session_state[version_key] = st.session_state.get(version_key, 0) + 1


def format_bytes(size: int) -> str:
    """Return a compact, readable byte count."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def collect_uploads(logo, cover, gallery, alt_texts: dict[str, str]) -> list[UploadedImage]:
    """Convert Streamlit uploaded files into processor inputs."""
    uploads: list[UploadedImage] = []
    if logo is not None:
        uploads.append(
            UploadedImage(
                logo.name,
                logo.getvalue(),
                ImageKind.LOGO,
                alt_text=alt_texts["logo"],
            )
        )
    if cover is not None:
        uploads.append(
            UploadedImage(
                cover.name,
                cover.getvalue(),
                ImageKind.COVER,
                alt_text=alt_texts["cover"],
            )
        )
    uploads.extend(
        UploadedImage(
            file.name,
            file.getvalue(),
            ImageKind.GALLERY,
            index,
            alt_texts[f"gallery_{index}"],
        )
        for index, file in enumerate(gallery or (), start=1)
    )
    return uploads


def show_alt_text_inputs(entity_name, logo, cover, gallery) -> dict[str, str]:
    """Show editable localized alt-text suggestions for selected images."""
    alt_texts: dict[str, str] = {}
    with st.expander("SEO alt text", expanded=True):
        st.caption(
            "These descriptions are used on the website, not embedded inside the image. "
            "Edit gallery descriptions to say what each photo actually shows."
        )
        if logo is not None:
            alt_texts["logo"] = st.text_input(
                "Logo alt text",
                value=suggest_alt_text(entity_name, ImageKind.LOGO),
                key="alt_text_logo",
                on_change=clear_last_result,
            )
        if cover is not None:
            alt_texts["cover"] = st.text_input(
                "Cover alt text",
                value=suggest_alt_text(entity_name, ImageKind.COVER),
                key="alt_text_cover",
                on_change=clear_last_result,
            )
        for index, file in enumerate(gallery or (), start=1):
            alt_texts[f"gallery_{index}"] = st.text_input(
                f"Gallery {index:02d} alt text · {file.name}",
                value=suggest_alt_text(entity_name, ImageKind.GALLERY, index),
                key=f"alt_text_gallery_{index}",
                on_change=clear_last_result,
            )
    return alt_texts


def show_preview(logo, cover, gallery) -> None:
    """Show compact previews of all selected files."""
    preview_items = []
    if logo is not None:
        preview_items.append(("Logo", logo))
    if cover is not None:
        preview_items.append(("Cover", cover))
    preview_items.extend(
        (f"Gallery {index:02d}", file)
        for index, file in enumerate(gallery or (), start=1)
    )
    if not preview_items:
        return

    with st.expander(f"Preview selected images ({len(preview_items)})", expanded=False):
        columns = st.columns(3)
        for index, (label, uploaded_file) in enumerate(preview_items):
            with columns[index % 3]:
                st.image(uploaded_file.getvalue(), caption=f"{label} · {uploaded_file.name}")


def show_results(result: BatchResult, entity_slug: str) -> None:
    """Render the summary table and download action for a completed batch."""
    st.success(
        f"Images have been SAVED successfully. "
        f"Processed {len(result.images)} image(s)."
    )

    first, second, third = st.columns(3)
    first.metric("Original size", format_bytes(result.original_bytes))
    second.metric("Optimized size", format_bytes(result.output_bytes))
    third.metric("Total reduction", f"{result.reduction_percent:.1f}%")

    rows = [
        {
            "Output filename": image.output_path.name,
            "Alt text": next(
                metadata.alt_text
                for metadata in result.seo_metadata
                if metadata.filename == image.output_path.name
            ),
            "Dimensions": (
                f"{image.original_size[0]}×{image.original_size[1]} → "
                f"{image.output_size[0]}×{image.output_size[1]}"
            ),
            "Before": format_bytes(image.original_bytes),
            "After": format_bytes(image.output_bytes),
            "Saved": f"{image.reduction_percent:.1f}%",
        }
        for image in result.images
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("Saved on this computer in:")
    st.code(str(result.output_folder.resolve()), language=None)
    zip_column, metadata_column = st.columns(2)
    with zip_column:
        st.download_button(
            "Download images and SEO data",
            data=result.zip_data,
            file_name=f"{entity_slug}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
    with metadata_column:
        st.download_button(
            "Download SEO metadata CSV",
            data=result.metadata_csv,
            file_name=result.metadata_path.name,
            mime="text/csv;charset=utf-8",
            use_container_width=True,
        )

    with st.expander("Website publishing data"):
        st.dataframe(
            [
                {
                    "Type": metadata.image_kind.value,
                    "Filename": metadata.filename,
                    "Alt text": metadata.alt_text,
                    "Encoded URL filename": metadata.url_encoded_filename,
                    "HTML example": metadata.html_example,
                }
                for metadata in result.seo_metadata
            ],
            use_container_width=True,
            hide_index=True,
        )


st.set_page_config(
    page_title="RAM World Image Optimizer",
    page_icon="🖼️",
    layout="centered",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 980px; padding-top: 2.5rem; padding-bottom: 4rem;}
    [data-testid="stFileUploader"] {border-radius: 12px;}
    div[data-testid="stMetric"] {
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 12px;
        padding: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("RAM World Image Optimizer")
st.write(
    "Optimize and rename event, company, or partner images for the web. "
    "Everything is saved together in one folder."
)

entity_name = st.text_input(
    "Event, company, or partner name",
    placeholder="Example: Riyadh Tech Summit",
    help="This name is used for the output folder and every SEO-friendly filename.",
    on_change=reset_after_source_change,
)

if entity_name.strip():
    try:
        slug_preview = slugify_name(entity_name)
        st.caption(
            f"Cover filename example: ramworld-{slug_preview}-cover.jpg"
        )
    except ValueError:
        slug_preview = ""
else:
    slug_preview = ""

st.subheader("Upload images")
for upload_type in ("logo", "cover", "gallery"):
    st.session_state.setdefault(f"{upload_type}_uploader_version", 0)

left, right = st.columns(2)
with left:
    logo_file = st.file_uploader(
        "Logo",
        type=ACCEPTED_IMAGE_TYPES,
        help="One logo. Transparent PNG files are supported.",
        on_change=reset_after_source_change,
        key=f"logo_uploader_{st.session_state.logo_uploader_version}",
    )
    st.button(
        "Clear logo",
        on_click=clear_uploader,
        args=("logo",),
        disabled=logo_file is None,
        use_container_width=True,
        key="clear_logo_button",
    )
with right:
    cover_file = st.file_uploader(
        "Cover",
        type=ACCEPTED_IMAGE_TYPES,
        help="One cover. Its filename will use the entered event name.",
        on_change=reset_after_source_change,
        key=f"cover_uploader_{st.session_state.cover_uploader_version}",
    )
    st.button(
        "Clear cover",
        on_click=clear_uploader,
        args=("cover",),
        disabled=cover_file is None,
        use_container_width=True,
        key="clear_cover_button",
    )

gallery_files = st.file_uploader(
    "Photo gallery",
    type=ACCEPTED_IMAGE_TYPES,
    accept_multiple_files=True,
    help="Select one or several gallery photos.",
    on_change=reset_after_source_change,
    key=f"gallery_uploader_{st.session_state.gallery_uploader_version}",
)

has_upload = bool(logo_file or cover_file or gallery_files)
clear_gallery_column, clear_all_column = st.columns(2)
with clear_gallery_column:
    st.button(
        "Clear gallery",
        on_click=clear_uploader,
        args=("gallery",),
        disabled=not gallery_files,
        use_container_width=True,
        key="clear_gallery_button",
    )
with clear_all_column:
    st.button(
        "Clear all uploads",
        on_click=clear_all_uploaders,
        disabled=not has_upload,
        use_container_width=True,
        key="clear_all_button",
    )

show_preview(logo_file, cover_file, gallery_files)

if entity_name.strip() and has_upload:
    alt_texts = show_alt_text_inputs(
        entity_name,
        logo_file,
        cover_file,
        gallery_files,
    )
else:
    alt_texts = {}

with st.expander("Advanced options"):
    overwrite = st.checkbox(
        "Replace files with the same generated name",
        value=False,
        help="Leave this disabled to protect images from accidental replacement.",
    )
    st.caption("Output folder: " + str(OUTPUT_ROOT.resolve()))

process_clicked = st.button(
    "Optimize and save images",
    type="primary",
    use_container_width=True,
    disabled=not (entity_name.strip() and has_upload),
)

if not entity_name.strip() or not has_upload:
    st.caption("Enter a name and upload at least one image to continue.")

if process_clicked:
    try:
        uploads = collect_uploads(
            logo_file,
            cover_file,
            gallery_files,
            alt_texts,
        )
        with st.spinner("Optimizing images…"):
            batch_result = process_uploaded_images(
                entity_name,
                OUTPUT_ROOT,
                uploads,
                overwrite=overwrite,
            )
        st.session_state["last_result"] = batch_result
        st.session_state["last_slug"] = slugify_name(entity_name)
    except (ValueError, FileExistsError, OSError) as exc:
        st.error(str(exc))

last_result = st.session_state.get("last_result")
last_slug = st.session_state.get("last_slug")
if last_result is not None and last_slug:
    st.divider()
    st.subheader("Results")
    show_results(last_result, last_slug)

with st.expander("Google Images publishing checklist"):
    st.markdown(
        """
        After uploading the generated files to the website:

        - Use the supplied alt text in a normal `<img src="…" alt="…">` element.
        - Place the image on a relevant Arabic page near descriptive Arabic text.
        - Give the page an accurate Arabic title and heading.
        - Ensure the page and image are public and not blocked from Google.
        - Add important images to the site's image sitemap and monitor Search Console.
        - Keep each image at one consistent URL wherever possible.

        The app prepares the files and metadata. The website or CMS must apply these
        publishing steps before Google can discover and index the images.
        """
    )
