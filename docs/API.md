# Local HTTP API v1

The local app listens on `http://127.0.0.1:8765`. Its interactive OpenAPI
documentation is at `/docs`, and the machine-readable schema is at
`/openapi.json`. This API saves to the filesystem of the machine running the
server. For uploads from another system, use the separate
[hosted API](HOSTED.md).

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/health` | Return `{"status":"ok"}`. |
| `POST /api/v1/process` | Optimize, name, and save one batch; return a temporary ZIP URL. |
| `GET /api/v1/download/{token}` | Download the saved images and SEO CSV as a ZIP. |

The former `/api/health`, `/api/process`, and `/api/download/{token}` routes
remain available for existing clients. New integrations should use `/api/v1`.
The local folder picker is a user-interface helper at `POST /api/select-folder`
and is not part of the versioned integration contract.

## Process request

Use `multipart/form-data`. The folder must already exist on the server machine.
Provide at least one image. Send multiple `gallery` fields for multiple gallery
images. Supported inputs are PNG, JPEG, WebP, and SVG; animated images are
rejected.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `output_folder` | string path | Yes | — |
| `entity_name` | project name | Yes | — |
| `logo` | file | No | — |
| `cover` | file | No | — |
| `gallery` | repeated file | No | — |
| `naming_language` | `english` or `arabic` | No | `english` |
| `filename_prefix` | string | No | Empty (no prefix) |
| `overwrite` | boolean | No | `false` |
| `logo_alt`, `cover_alt` | string | No | Generated suggestion |
| `gallery_alt` | JSON array of strings | No | `[]` |

An explicitly blank alt text remains blank. `gallery_alt` entries correspond
to gallery files in upload order; missing entries receive suggestions. The
response lists only images processed in this request, while its ZIP also
includes previously processed images tracked by the project's SEO CSV.
`filename_prefix` is normalized to a safe slug: `My Brand` becomes `my-brand`.
It prefixes image filenames, while the SEO CSV stays named for the project.

### Example with Python

Install `httpx` for this example (`pip install httpx`). Start the local app,
then run:

```python
from pathlib import Path
import httpx

with Path("cover.jpg").open("rb") as cover:
    response = httpx.post(
        "http://127.0.0.1:8765/api/v1/process",
        data={
            "output_folder": r"C:\Images",
            "entity_name": "Riyadh Tech Summit",
            "naming_language": "english",
            "filename_prefix": "my-brand",
        },
        files={"cover": ("cover.jpg", cover, "image/jpeg")},
        timeout=120,
    )
response.raise_for_status()
result = response.json()
print(result["images"][0]["filename"])

zip_response = httpx.get(
    "http://127.0.0.1:8765" + result["download_url"], timeout=120
)
zip_response.raise_for_status()
Path("riyadh-tech-summit.zip").write_bytes(zip_response.content)
```

### Example with JavaScript

Run this in a page served from the same origin as the local app, with a file
input named `coverFile`:

```javascript
const data = new FormData();
data.append("output_folder", "C:\\Images");
data.append("entity_name", "Riyadh Tech Summit");
data.append("filename_prefix", "my-brand");
data.append("cover", coverFile, coverFile.name);

const response = await fetch("/api/v1/process", { method: "POST", body: data });
const result = await response.json();
if (!response.ok) throw new Error(result.detail ?? "Processing failed");
console.log(result.images[0].filename, result.download_url);
```

## Response and errors

On success, `POST /api/v1/process` returns `200` with:

```json
{
  "message": "Images have been saved successfully.",
  "output_folder": "C:\\Images\\riyadh-tech-summit",
  "original_bytes": 120000,
  "output_bytes": 42000,
  "reduction_percent": 65.0,
  "download_url": "/api/v1/download/<token>",
  "images": [
    {
      "filename": "my-brand-riyadh-tech-summit-cover.webp",
      "alt_text": "Riyadh Tech Summit cover",
      "original_bytes": 120000,
      "output_bytes": 42000,
      "original_size": [1600, 900],
      "output_size": [1600, 900],
      "reduction_percent": 65.0
    }
  ]
}
```

These numbers illustrate the response shape; actual values depend on the file.

| Status | Meaning |
| --- | --- |
| `400` | Invalid folder, name, options, image, or existing output filename. Returns `{"detail":"..."}`. |
| `404` | Unknown or evicted ZIP token. Returns `{"detail":"This download has expired."}`. |
| `422` | Missing required form field or invalid field type. Returns FastAPI validation details. |

Downloads are held in process memory; the oldest token is removed after ten
batches or when the app restarts. The local server is bound to `127.0.0.1` by
the supplied launchers. If you need to expose an API to other machines, add
authentication, upload limits, controlled storage, and download lifecycle
management before deployment.
