# Hosted API

The hosted API is a separate FastAPI application. It does not mount the local
folder picker, local browser UI, or `/api/v1` routes. Clients cannot choose a
filesystem path. They upload images to `POST /api/v2/process`, and the service
saves them below one configured storage root.

This deployment model is for one trusted integration or team sharing a secret.
It does not provide separate users, projects, or tenant permissions.

## Start the service

Install Python 3.11+ and the optional web dependencies:

```powershell
python -m pip install -e ".[web]"
```

Generate a token and set a dedicated absolute storage directory. On Windows
PowerShell:

```powershell
$env:IMAGE_SEO_API_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:IMAGE_SEO_STORAGE_ROOT = "C:\ImageSeoStorage"
python -m uvicorn image_seo_tool.hosted:create_hosted_app --factory --host 127.0.0.1 --port 8766
```

Set the same token in the integrating application. For access from other
machines, place the service behind an HTTPS reverse proxy and keep the token
out of browser code and source control. Run a single worker until you add
concurrency control for updates to the same project folder. Use a disk quota
for the storage volume if the service will receive many projects.

The server fails to start if either required environment variable is absent,
the storage path is relative, or the token is shorter than 32 characters.

## Request

`POST /api/v2/process` accepts `multipart/form-data` with:

| Field | Type | Default |
| --- | --- | --- |
| `entity_name` | Project name, required | — |
| `logo` | One JPEG, PNG, or WebP file | — |
| `cover` | One JPEG, PNG, or WebP file | — |
| `gallery` | Repeated JPEG, PNG, or WebP files | — |
| `naming_language` | `english` or `arabic` | `english` |
| `filename_prefix` | Optional custom text | Empty |
| `overwrite` | Boolean | `false` |
| `logo_alt`, `cover_alt` | Optional alt text | Suggested text |
| `gallery_alt` | JSON array of strings | `[]` |

At least one image is required. Set `Authorization: Bearer <token>` for both
processing and ZIP downloads. SVG is deliberately rejected in the hosted API;
the local application continues to support it. The hosted service re-encodes
raster files, so it does not return original source bytes with embedded EXIF.

Example using Python and `httpx`:

```python
from pathlib import Path
import httpx

base_url = "https://images.example.com"
token = "your-secret-token-from-the-server"
headers = {"Authorization": f"Bearer {token}"}

with Path("cover.jpg").open("rb") as cover:
    response = httpx.post(
        base_url + "/api/v2/process",
        headers=headers,
        data={"entity_name": "My Project", "filename_prefix": "My Brand"},
        files={"cover": ("cover.jpg", cover, "image/jpeg")},
        timeout=120,
    )
response.raise_for_status()
result = response.json()
print(result["images"][0]["filename"])

zip_response = httpx.get(base_url + result["download_url"], headers=headers)
zip_response.raise_for_status()
Path("optimized-images.zip").write_bytes(zip_response.content)
```

The response contains `project_slug`, aggregate size metrics, a temporary
`download_url`, and image summaries. It does not reveal the server's storage
path. The ZIP contains images tracked by the project's SEO CSV.

## Limits and errors

The defaults are 32 MiB per request, 10 MiB per file, 12 files per request,
20 million pixels per image, 64 MiB of stored files per project, and a one-hour
ZIP download lifetime. See [Configuration](CONFIGURATION.md) for environment
variables that change these limits.

| Status | Meaning |
| --- | --- |
| `400` | Invalid project name, options, or image; or an output name already exists. |
| `401` | Missing or incorrect bearer token. |
| `404` | Download token not found or expired. |
| `413` | Request, file, image count, or project storage limit exceeded. |
| `415` | SVG upload. |
| `422` | Missing required form field or invalid field type. |

Request bytes are counted before multipart parsing, including when the client
omits `Content-Length`. Files are read in bounded chunks. ZIPs are stored under
`<storage root>/.downloads` and expire after the configured lifetime. Expired
ZIPs are removed on startup and on subsequent processing or download requests.
Project image folders are persistent until an operator removes them.

`GET /api/v2/health` is public. The OpenAPI schema is at `/openapi.json`, and
interactive documentation is at `/docs`.
