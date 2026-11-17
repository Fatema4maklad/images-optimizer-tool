# Configuration

## Python processing core

`ToolConfig` is validated when constructed and is accepted by `process_images`,
`process_uploaded_images`, `process_image_file`, and `process_image_set`.

```python
from dataclasses import replace
from image_seo_tool import ImageKind, NamingLanguage, OptimizationSettings, ToolConfig

defaults = ToolConfig()
custom = replace(
    defaults,
    naming_language=NamingLanguage.ARABIC,
    filename_prefix="My Brand",
    settings={
        **defaults.settings,
        ImageKind.COVER: OptimizationSettings(1600, 900, 85),
    },
)
```

| Option | Default | Meaning |
| --- | --- | --- |
| `naming_language` | `english` | Language of type labels in filenames. |
| `filename_prefix` | Empty | Optional normalized prefix on image filenames. |
| `include_kind_label` | `True` | Set to `False` for numbered filenames without logo, cover, or gallery labels. |
| `labels` | English and Arabic logo, cover, gallery labels | Custom labels by language and image type. |
| `settings` | See table below | Maximum dimensions and quality by image type. |
| `target_formats` | Logo original; cover/gallery WebP | Raster output format per type: `original`, `JPEG`, `PNG`, or `WEBP`. |
| `max_pixels` | None | Reject inputs over this number of pixels. |
| `preserve_original_bytes` | `True` | Keep unchanged source bytes when re-encoding would be larger. |

| Type | Maximum dimensions | Quality |
| --- | --- | --- |
| Logo | 1200 × 1200 | 95 |
| Cover | 1920 × 1080 | 88 |
| Gallery | 1920 × 1920 | 88 |

SVG input remains SVG in the core and local application. The hosted API rejects
SVG. Its processing configuration sets `preserve_original_bytes=False` to avoid
returning original raster bytes with embedded metadata.

## Hosted API environment

`IMAGE_SEO_STORAGE_ROOT` and `IMAGE_SEO_API_TOKEN` are required. Other settings
have defaults. Set them before starting the hosted app factory.

| Variable | Default | Meaning |
| --- | --- | --- |
| `IMAGE_SEO_STORAGE_ROOT` | Required | Absolute directory for project images and temporary ZIPs. |
| `IMAGE_SEO_API_TOKEN` | Required | Shared bearer token of at least 32 non-space characters. |
| `IMAGE_SEO_MAX_REQUEST_BYTES` | `33554432` | Maximum entire HTTP request body. |
| `IMAGE_SEO_MAX_FILE_BYTES` | `10485760` | Maximum bytes per image. |
| `IMAGE_SEO_MAX_FILES` | `12` | Maximum images in one request. |
| `IMAGE_SEO_MAX_IMAGE_PIXELS` | `20000000` | Maximum width × height per image. |
| `IMAGE_SEO_MAX_PROJECT_BYTES` | `67108864` | Maximum stored bytes in one project folder. |
| `IMAGE_SEO_DOWNLOAD_TTL_SECONDS` | `3600` | Lifetime of a ZIP download. |

The per-file limit cannot exceed the request limit. Invalid settings cause
startup to fail. The local browser application does not use these hosted
settings and continues to save to a folder selected by its user.
