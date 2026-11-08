# Image SEO Optimizer

A local tool and reusable Python package for preparing website images. It
resizes and optimizes uploads, gives them readable filenames, suggests alt text,
and creates a CSV and ZIP for publishing. It works with any project name.

## Output names

The default has no prefix. For a project named `Riyadh Tech Summit`, the output
looks like this:

```text
output/
└── riyadh-tech-summit/
    ├── riyadh-tech-summit-logo.png
    ├── riyadh-tech-summit-cover.webp
    ├── riyadh-tech-summit-gallery-01.webp
    ├── riyadh-tech-summit-gallery-02.webp
    └── riyadh-tech-summit-image-seo.csv
```

The optional **Filename prefix** field adds your own label to image filenames.
For example, `My Brand` produces `my-brand-riyadh-tech-summit-cover.webp`.
Spaces and punctuation are normalized for filenames. The project folder and
SEO CSV keep the project name, so one metadata file tracks images processed in
the folder. Arabic project names and Arabic filename labels remain readable in
Arabic. The prefix is optional in both languages.

## Image rules

| Type | Maximum dimensions | Default quality | Output format |
| --- | --- | --- | --- |
| Logo | 1200 × 1200 | 95 | Original format |
| Cover | 1920 × 1080 | 88 | WebP |
| Gallery | 1920 × 1920 | 88 | WebP |

Supported uploads are JPEG, PNG, WebP, and SVG. Raster images keep their aspect
ratio and are never enlarged. SVGs remain SVG. Logo transparency is preserved.
If re-encoding an unchanged image would make it larger, the original bytes are
kept. Animated images are not supported.

The interface suggests editable English or Arabic alt text. The UTF-8 SEO CSV
contains each filename, alt text, URL-encoded filename, and an HTML `<img>`
example. Alt text can be cleared deliberately. Existing generated image names
are protected unless **Replace files with the same generated name** is selected.

## Run locally

Python 3.11 or newer is required. On Windows, create the environment once:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Then double-click `start_app.bat`. It opens the local browser interface at
`http://127.0.0.1:8765`. Choose an existing destination folder, enter a
project name, add a logo, cover, and/or gallery images, then optimize. Results
are saved in a project folder and can also be downloaded as a ZIP.

On macOS, double-click `start_app.command`. The first launch creates a separate
environment and installs the web dependencies. If macOS says the launcher is
not executable, run `chmod +x start_app.command` in the project folder once.

Run the automated tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The interface has drag-and-drop previews, editable alt text, a clear button
for each upload, a results dialog, and a persistent light/dark theme switch.

## Integrate the Python core

The core requires only Pillow and python-slugify. It does not import FastAPI
and does not write files. `process_images` returns processed bytes and metadata
that another application can save to its own media library or object storage.

```python
from image_seo_tool import ImageKind, UploadedImage, process_images

result = process_images(
    "Riyadh Tech Summit",
    [UploadedImage("cover.jpg", uploaded_bytes, ImageKind.COVER)],
)
for asset in result.assets:
    media_library.save(asset.filename, asset.data, content_type=asset.mime_type)
```

Pass `ToolConfig(filename_prefix="My Brand")` to add a prefix. The same
configuration can set filename language, image labels, size limits, quality,
and output formats. `process_uploaded_images` is the local filesystem and ZIP
adapter. `process_image_file` and `process_image_set` support local file paths.

Install `.[web]` for the FastAPI interface or `.[dev]` for the interface and
tests. The [local HTTP API contract](docs/API.md) documents the versioned
endpoints and examples. The API is intended to run on the same computer as the
destination folder.

For server-side integrations, use the separate authenticated
[hosted API](docs/HOSTED.md). It controls its own storage root, limits uploads,
and expires ZIP downloads. See the [integration guide](docs/INTEGRATION.md),
[configuration reference](docs/CONFIGURATION.md), and [changelog](CHANGELOG.md)
for the supported interfaces and release history.

made by Eng. Fatem ★
