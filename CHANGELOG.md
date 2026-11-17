# Changelog

This project records user-visible changes here. Versions are set in
`pyproject.toml` and the two FastAPI app definitions before a release.

## Unreleased

- Added English and Arabic interfaces for the local and public tools, with
  Arabic as the first-run default and a persistent language switch.
- Added a separate simple upload page with image previews, numbered WebP
  filenames, individual downloads, and an all-images ZIP.
- Restricted local browser requests to loopback hosts and same-origin writes.
- Raised the Pillow minimum to 13.0.0 for current security fixes.
- Renamed the reusable package to `image_seo_tool` and removed built-in brand
  prefixes. New filenames have no prefix unless one is supplied.
- Added a project-neutral interface using Times New Roman and an optional
  custom filename prefix.
- Added a separate authenticated hosted API with request, file, pixel, file
  count, and project storage limits. Hosted uploads reject SVG.
- Added expiring disk-backed ZIP downloads for the hosted API.
- Documented the Python, local HTTP, and hosted HTTP integrations and their
  configuration.

## 0.1.0

- Initial local image optimization application.
