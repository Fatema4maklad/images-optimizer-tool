# Changelog

This project records user-visible changes here. Versions are set in
`pyproject.toml` and the two FastAPI app definitions before a release.

## Unreleased

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
