# RAM World Image Tool

An internal Python application for optimizing company, event, and partner images,
renaming them consistently, and placing them in one easy-to-access folder.

## Output convention

For an input name such as `Al Riyadh Company`, the tool creates:

```text
output/
+-- al-riyadh-company/
    +-- ramworld-al-riyadh-company-logo.png
    +-- ramworld-al-riyadh-company-cover.webp
    +-- ramworld-al-riyadh-company-gallery-01.webp
    +-- ramworld-al-riyadh-company-gallery-02.webp
    +-- ramworld-al-riyadh-company-image-seo.csv
```

Arabic names stay in Arabic. For `منتدى الرياض الاقتصادي`, the cover is named
`ramworld-منتدى-الرياض-الاقتصادي-cover.webp` and is placed in the folder
`منتدى-الرياض-الاقتصادي`.

The interface includes an English/Arabic filename-language selector. Arabic
naming uses `عالم-رام`, `شعار`, `الغلاف`, and `صور`, for example:

```text
عالم-رام-منتدى-الرياض-الاقتصادي-شعار.png
عالم-رام-منتدى-الرياض-الاقتصادي-الغلاف.webp
عالم-رام-منتدى-الرياض-الاقتصادي-صور-01.webp
```

The **RAM World prefix** option controls whether generated names begin with
`ramworld-` (or `عالم-رام-` in Arabic). Choose **Exclude** to create names such
as `riyadh-tech-summit-cover.webp` while keeping the same output folder.

## Workflow

1. Enter the event, company, or partner name.
2. Upload one logo, one cover image, and multiple gallery images.
3. Preview the output names and optimization settings.
4. Optimize and save every image in the entity's single output folder.

The entered name is used for the cover filename. For example, the cover for
`Riyadh Tech Summit` is saved as `ramworld-riyadh-tech-summit-cover.webp`.

## Default image limits

| Type | Maximum dimensions | Default quality |
| --- | --- | --- |
| Logo | 1200 x 1200 | 95 |
| Cover | 1920 x 1080 | 88 |
| Gallery | 1920 x 1920 | 88 |

Images keep their aspect ratio and are never enlarged. PNG optimization is
lossless, logo transparency is preserved, and an already optimized image is
kept unchanged when re-encoding would make it larger.

Raster covers and gallery photos are converted to high-quality WebP for smaller
web downloads. SVG files remain SVG, and logos retain their uploaded format, so
transparent PNG and vector branding are not unnecessarily converted.

## Run the application

On Windows, double-click `start_app.bat`. The application opens in your web
browser. Select the destination folder first using the native folder picker or
by pasting its path. The tool creates the event/company folder inside that
location. Results can also be downloaded together as a ZIP file.

On macOS, install Python 3.11 or newer once, then double-click
`start_app.command`. The first launch creates a separate Mac environment and
installs the required packages automatically, so it can take a minute. Later
launches open immediately. If macOS reports that the launcher is not
executable, open Terminal in the project folder and run this once:

```bash
chmod +x start_app.command
```

The interface provides editable Arabic or English alt-text suggestions. It also
creates a UTF-8 SEO metadata CSV containing each filename, alt text, URL-encoded
filename, and an HTML `<img>` example for the website team.

The SEO alt-text section is optional and collapsed by default. Users can accept
the suggestions without opening it, edit them, or clear a field for blank alt
text.

Each upload area has a clear button, and `Clear all` empties the entire
form. After processing, the interface explicitly confirms that the images were
saved successfully and shows the destination folder.

The interface is a standard local website with a compact, responsive layout
and a persistent light/dark mode switch. Each image preview appears immediately
inside the same box used to select or drop the file. The gallery box shows up
to six thumbnails and a count for the remaining images. Results open in a
dialog so the main workflow stays short.

made by Eng. fatem ★

For command-line use:

```powershell
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8765
```
