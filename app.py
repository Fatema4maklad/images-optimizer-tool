"""Streamlit interface for the RAM World image optimization tool."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import streamlit as st

from ramworld_image_tool import (
    BatchResult,
    ImageKind,
    NamingLanguage,
    UploadedImage,
    build_filename,
    process_uploaded_images,
    slugify_name,
    suggest_alt_text,
)


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


def browse_for_output_folder() -> None:
    """Open the Windows folder picker and store the selected destination."""
    powershell_script = r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Choose where processed image folders will be saved'
$dialog.ShowNewFolderButton = $true
if ($env:RAMWORLD_INITIAL_FOLDER -and (Test-Path -LiteralPath $env:RAMWORLD_INITIAL_FOLDER)) {
    $dialog.SelectedPath = $env:RAMWORLD_INITIAL_FOLDER
}
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
$owner.Dispose()
$dialog.Dispose()
"""
    picker_environment = os.environ.copy()
    picker_environment["RAMWORLD_INITIAL_FOLDER"] = st.session_state.get(
        "output_folder_path", ""
    )
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-STA",
                "-Command",
                powershell_script,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=picker_environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        st.session_state["folder_picker_error"] = (
            f"The folder picker could not open: {exc}"
        )
        return

    selected_path = completed.stdout.strip().lstrip("\ufeff")
    if selected_path:
        st.session_state["output_folder_path"] = selected_path
        st.session_state.pop("folder_picker_error", None)
        reset_after_source_change()
    elif completed.returncode != 0:
        st.session_state["folder_picker_error"] = (
            "The folder picker could not open. You can paste the folder path instead."
        )


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


def show_alt_text_inputs(
    entity_name,
    logo,
    cover,
    gallery,
    naming_language: NamingLanguage,
) -> dict[str, str]:
    """Show editable localized alt-text suggestions for selected images."""
    alt_texts: dict[str, str] = {}
    with st.expander("SEO alt text (optional)", expanded=False):
        st.caption(
            "You can use the suggestions, edit them, or clear a field to leave its "
            "alt text blank. Gallery descriptions should say what each photo shows."
        )
        if logo is not None:
            alt_texts["logo"] = st.text_input(
                "Logo alt text",
                value=suggest_alt_text(
                    entity_name, ImageKind.LOGO, language=naming_language
                ),
                key="alt_text_logo",
                on_change=clear_last_result,
            )
        if cover is not None:
            alt_texts["cover"] = st.text_input(
                "Cover alt text",
                value=suggest_alt_text(
                    entity_name, ImageKind.COVER, language=naming_language
                ),
                key="alt_text_cover",
                on_change=clear_last_result,
            )
        for index, file in enumerate(gallery or (), start=1):
            alt_texts[f"gallery_{index}"] = st.text_input(
                f"Gallery {index:02d} alt text · {file.name}",
                value=suggest_alt_text(
                    entity_name,
                    ImageKind.GALLERY,
                    index,
                    naming_language,
                ),
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

st.subheader("1. Select output folder")
output_path_column, browse_column = st.columns([4, 1])
with output_path_column:
    selected_output_text = st.text_input(
        "Output folder",
        placeholder="Example: C:\\Users\\YourName\\Pictures\\RAM World",
        key="output_folder_path",
        on_change=reset_after_source_change,
        help="A separate event or company folder will be created inside this location.",
    )
with browse_column:
    st.write("")
    st.write("")
    st.button(
        "Browse…",
        on_click=browse_for_output_folder,
        use_container_width=True,
        key="browse_output_folder_button",
    )

if picker_error := st.session_state.get("folder_picker_error"):
    st.error(picker_error)

if not selected_output_text.strip():
    st.info("Select an output folder before entering the image details.")
    st.stop()

selected_output_root = Path(selected_output_text.strip()).expanduser()
if not selected_output_root.is_dir():
    st.error("The selected output folder does not exist or is not a folder.")
    st.stop()

st.success(f"Output folder selected: {selected_output_root.resolve()}")

st.subheader("2. Name and language")
entity_name = st.text_input(
    "Event, company, or partner name",
    placeholder="Example: Riyadh Tech Summit",
    help="This name is used for the output folder and every SEO-friendly filename.",
    on_change=reset_after_source_change,
)

language_choice = st.radio(
    "Filename language / لغة أسماء الملفات",
    options=("English", "العربية"),
    horizontal=True,
    on_change=reset_after_source_change,
    key="naming_language_choice",
)
naming_language = (
    NamingLanguage.ARABIC
    if language_choice == "العربية"
    else NamingLanguage.ENGLISH
)
st.caption(
    "Arabic: عالم رام / شعار / الغلاف / صور"
    if naming_language is NamingLanguage.ARABIC
    else "English: ramworld / logo / cover / gallery"
)

if entity_name.strip():
    try:
        cover_filename_preview = build_filename(
            entity_name,
            ImageKind.COVER,
            "webp",
            language=naming_language,
        )
        st.caption(f"Cover filename example: {cover_filename_preview}")
    except ValueError:
        pass

st.subheader("3. Upload images")
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
st.caption(
    "Covers and gallery photos are converted to high-quality WebP. "
    "Logos keep their original format."
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
        naming_language,
    )
else:
    alt_texts = {}

with st.expander("Advanced options"):
    overwrite = st.checkbox(
        "Replace files with the same generated name",
        value=False,
        help="Leave this disabled to protect images from accidental replacement.",
    )
    st.caption("Output folder: " + str(selected_output_root.resolve()))

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
                selected_output_root,
                uploads,
                naming_language=naming_language,
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

st.divider()
st.caption("made by Eng. fatem ★")
