# Simple public interface

This is a separate web app for people who need to optimize a small set of
images quickly. Its display name is intentionally undecided. The current page
uses a descriptive heading and shows “Developed by Fatema Maklad” in its footer.
The page supports English and Arabic, starts in Arabic on first use, and
remembers the visitor's interface choice. Filename language is a separate setting.

## Run locally

Install the web dependencies from the project root, then choose an absolute
storage directory. On Windows PowerShell:

```powershell
py -3.13 -m pip install -e ".[web]"
$env:IMAGE_SEO_PUBLIC_STORAGE_ROOT = (New-Item -ItemType Directory -Force .public-storage).FullName
py -3.13 -m uvicorn image_seo_tool.public_app:create_public_app --factory --host 127.0.0.1 --port 8770
```

Open `http://127.0.0.1:8770`. The original local app still runs on its own
port with its existing output-folder workflow.

## What it does

- Takes a project name, optional filename prefix, English or Arabic filename
  setting, and one multi-image upload field.
- Accepts 1–12 JPEG, PNG, or WebP files, up to 10 MB each and 20 million pixels.
- Converts all results to WebP. Names are `project-01.webp`, `project-02.webp`,
  etc., or `prefix-project-01.webp` when a prefix is entered. No image type
  appears in the name.
- Shows selected-image and result previews. Each result can be downloaded
  separately. “Download all” returns a ZIP with the images and a UTF-8 SEO CSV.
- Keeps each request in its own temporary ZIP with an unguessable link. Links
  expire after one hour. The storage root must be writable and should be
  periodically monitored and backed by enough free space.

The reusable processing library remains independent of FastAPI and storage.
The public app owns only form handling, request limits, result presentation,
and short-lived downloads. Processing settings and limits live in
`PublicSettings` and `ToolConfig`.

## API

`POST /api/public/process` accepts multipart form fields `project_name`,
`filename_prefix`, `naming_language`, and repeated `images` files. The JSON
response provides per-image preview and download URLs plus `download_all_url`.
`GET /api/public/health` returns service status. The app also exposes OpenAPI
at `/docs` and `/openapi.json`.

## Before opening it to the Internet

The app has per-request size limits and expiring downloads. A public deployment
also needs HTTPS, a reverse proxy with rate limiting, a disk quota/monitoring,
and a decision about abuse prevention and privacy. Download links act as
temporary access tokens, so anyone who receives a link can access that result
until it expires. Run one instance per storage root or use shared storage for
multiple instances. This basic version has no account system or background
queue.
