# محسّن الصور

أداة لتجهيز صور المواقع وتحسين سرعة تحميل الصفحات. تضغط الصور
وتضبط أبعادها وصيغتها لتقليل حجمها، وتمنحها أسماء واضحة ونصوصًا بديلة مقترحة
تساعد على تنظيمها وتهيئتها لمحركات البحث. ثم تُنشئ ملف CSV لبيانات الصور وملف
ZIP للتنزيل. تعمل بالعربية والإنجليزية؛ **العربية هي لغة الواجهة عند التشغيل
الأول**، ويمكن تغييرها من الزر أعلى الصفحة. لغة الواجهة مستقلة عن لغة أسماء
الملفات.

## ما الموجود في المشروع؟

| الجزء | الاستخدام |
| --- | --- |
| الأداة المحلية | تعمل على جهازك وتحفظ الصور في مجلد تختاره. تدعم الشعار والغلاف ومعرض الصور وملفات SVG. |
| مكتبة Python | تسمح للمطوّر باستدعاء معالجة الصور مباشرة من نظامه وحفظ النتائج بالطريقة المناسبة له. |
| واجهة API للخوادم | تسمح لنظام آخر بإرسال الصور من خلفيته باستخدام مفتاح سري، ثم استلام النتائج. |
| واجهة الرفع المبسطة | تجربة منفصلة لرفع عدة صور في حقل واحد ومعاينتها وتنزيلها منفردة أو في ZIP. لم تُنشر على موقع بعد. |

## تشغيل الأداة المحلية

يلزم Python 3.11 أو أحدث. على Windows، افتح PowerShell داخل مجلد المشروع وشغّل
الأوامر التالية مرة واحدة:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[web]"
```

بعد ذلك شغّل `start_app.bat`، وافتح `http://127.0.0.1:8765` إذا لم تُفتح
الصفحة تلقائيًا. على macOS شغّل `start_app.command`؛ سيُعدّ بيئة العمل في
التشغيل الأول. إذا لم يسمح النظام بفتحه، نفّذ `chmod +x start_app.command`
مرة واحدة.

اختر مجلد الحفظ واسم المشروع والصور، ثم اضغط زر التحسين. لا تُضاف أي بادئة
لأسماء الملفات إلا إذا كتبتها في الحقل الاختياري. أسماء الشعار والغلاف وصور
المعرض تتبع النوع في الأداة المحلية؛ الواجهة المبسطة تستخدم أسماء مرقّمة مثل
`sample-project-01.webp` دون نوع الصورة.

## الصور والنتائج

تقبل الأداة المحلية صور JPEG وPNG وWebP وSVG. تحافظ على أبعاد الصورة النسبية
ولا تكبّر الصور الصغيرة. يبقى ملف SVG بصيغته، ويظل الشعار بصيغته الأصلية،
بينما يُحوَّل الغلاف وصور المعرض إلى WebP. تقترح الواجهة نصوصًا بديلة بالعربية
أو الإنجليزية يمكنك تعديلها أو حذفها. يحتوي ملف CSV بصيغة UTF-8 على أسماء
الصور والنصوص البديلة وأمثلة HTML. تحتاج إلى تفعيل خيار الاستبدال إذا أردت
الكتابة فوق ملف موجود يحمل الاسم الناتج نفسه.

أقصى أبعاد الشعار 1200 × 1200 بكسل، والغلاف 1920 × 1080، وصور المعرض
1920 × 1920. الواجهة المبسطة تقبل من صورة واحدة إلى 12 صورة JPEG أو PNG أو
WebP، بحجم لا يزيد على 10 ميغابايت و20 مليون بكسل للصورة الواحدة.

لتشغيل الاختبارات على Windows بعد تثبيت متطلبات التطوير باستخدام
`py -3.13 -m pip install -e ".[dev]"`، نفّذ:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## للمطوّرين

توجد تفاصيل الربط في [دليل التكامل](docs/INTEGRATION.md)، وإعدادات الخادم في
[دليل واجهة API](docs/HOSTED.md)، وطريقة تشغيل [واجهة الرفع المبسطة](docs/PUBLIC_INTERFACE.md).
الأداة المحلية ليست خادمًا عامًا؛ واجهة API المنفصلة هي المخصصة للربط من خلفية
موقع آخر.
مكتبة Python الأساسية تعالج الصور في الذاكرة وتعيد البيانات الناتجة لكي يحفظها
النظام الذي يستدعيها في وسائطه أو مخزنه. يمكن تثبيت متطلبات الويب بـ`.[web]`
أو متطلبات الويب والاختبارات بـ`.[dev]`. راجع أيضًا [مرجع الإعدادات](docs/CONFIGURATION.md)
و[سجل التغييرات](CHANGELOG.md).

## دليل الوثائق

| الوثيقة | ما توضحه |
| --- | --- |
| [دليل التكامل](docs/INTEGRATION.md) | اختيار طريقة الربط مع نظام آخر، واستدعاء مكتبة Python، وحفظ الصور الناتجة. |
| [واجهة API المحلية](docs/API.md) | طلبات الأداة التي تعمل على جهاز المستخدم واستجاباتها. |
| [واجهة API للخوادم](docs/HOSTED.md) | تشغيل الخدمة المحمية بمفتاح سري وربطها بخلفية موقع آخر؛ نقطة البداية لاستضافة خدمة التكامل مستقبلًا. |
| [واجهة الرفع المبسطة](docs/PUBLIC_INTERFACE.md) | تشغيل واجهة الرفع المنفصلة محليًا ومتطلبات اختبارها واستضافتها مستقبلًا. |
| [مرجع الإعدادات](docs/CONFIGURATION.md) | حدود الملفات والأبعاد والجودة والصيغ وخيارات التسمية والتخزين. |
| [إجراءات الإصدار](docs/RELEASING.md) | الاختبارات وبناء الحزمة والتحقق منها قبل إصدار نسخة جديدة. |
| [سجل التغييرات](CHANGELOG.md) | التعديلات التي أُضيفت إلى المشروع عبر الإصدارات. |

## English

# Image Optimizer

There is also a separate [simple public interface](docs/PUBLIC_INTERFACE.md) with
one image upload field, previews, and individual or ZIP downloads. It uses the
same processing core and leaves the existing local workflow intact.

A local tool and reusable Python package for preparing website images. It
reduces image weight to support faster page loads, resizes and converts uploads,
gives them readable filenames, suggests alt text,
and creates a CSV and ZIP for publishing. It works with any project name.

## Documentation guide

| Document | What it covers |
| --- | --- |
| [Integration guide](docs/INTEGRATION.md) | Choosing an integration path, calling the Python library, and saving results in another system. |
| [Local API](docs/API.md) | Requests and responses for the tool running on a user's computer. |
| [Hosted API](docs/HOSTED.md) | Running the token-protected service for backend integrations and planning its future hosting. |
| [Simple upload interface](docs/PUBLIC_INTERFACE.md) | Running the separate page locally and preparing a future test or public deployment. |
| [Configuration](docs/CONFIGURATION.md) | File and image limits, quality, formats, naming, and storage settings. |
| [Release process](docs/RELEASING.md) | Tests, package checks, and steps for a new release. |
| [Changelog](CHANGELOG.md) | Changes made across project versions. |

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
For example, `Example Brand` produces `example-brand-riyadh-tech-summit-cover.webp`.
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
On Windows, **Browse** opens the standard Explorer folder picker. You can also
paste a destination folder path into the field.
The project name is included in the output folder, image names, and metadata CSV.
The optional filename prefix is added only when you enter one. Existing files
from earlier runs remain in the same project folder.

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

Pass `ToolConfig(filename_prefix="Example Brand")` to add a prefix. The same
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
