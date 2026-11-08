# Integration guide

Choose one interface and keep the processing rules in one `ToolConfig`.

| Integration | Use when | Entry point |
| --- | --- | --- |
| Python package | Your application runs Python and controls storage. | `image_seo_tool.process_images` |
| Local HTTP API | A person runs the browser app and chooses a folder on that computer. | `/api/v1/process` |
| Hosted HTTP API | A server-side application uploads images to a shared service. | `/api/v2/process` |

## Python package

`process_images` does not save files. It returns a `ProcessingResult` with
`assets` and `seo_metadata`. Each asset has `filename`, `data`, `mime_type`,
`alt_text`, `original_size`, `output_size`, and byte counts. Save the bytes in
your own media library and attach the alt text to its record.

```python
from image_seo_tool import ImageKind, ToolConfig, UploadedImage, process_images

result = process_images(
    "My Project",
    [UploadedImage("cover.jpg", uploaded_bytes, ImageKind.COVER)],
    config=ToolConfig(filename_prefix="my-brand"),
)
for asset in result.assets:
    media_library.save(
        name=asset.filename,
        content=asset.data,
        content_type=asset.mime_type,
        alt_text=asset.alt_text,
    )
```

The example `media_library` represents your application's storage API. The
package does not supply one. `save_processed_result` is available if you want
the package's folder, CSV, and ZIP convention in your own Python application.

## HTTP APIs

The [local API](API.md) accepts a destination path on the same computer. The
[hosted API](HOSTED.md) uses a configured server storage root and bearer token;
clients cannot set a path. Both return image summaries and a ZIP download URL.
Use the hosted API from a server-side integration so its token stays secret.

Store each returned filename and alt text alongside the URL assigned by your
CMS or storage system. The CSV's sample `<img>` tag contains a filename, not
the final public URL. The integrating system is responsible for publishing the
image and writing that final URL into its page content.
