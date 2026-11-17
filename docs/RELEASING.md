# Release process

1. Update `CHANGELOG.md`: move completed items from **Unreleased** into a
   dated version section.
2. Set the same version in `pyproject.toml` and
   `src/image_seo_tool/version.py`. Review API paths separately when a request or
   response contract changes.
3. Run `python -m pytest -q`, `node --check web/app.js`,
   `node --check src/image_seo_tool/public_web/app.js`, and
   `node --check src/image_seo_tool/i18n/strings.js`. Smoke test both browser
   interfaces in English and Arabic, including right-to-left layout and
   filenames with and without a custom prefix.
4. Build a wheel with `python -m build` in an environment with the build
   dependencies installed. Inspect it to confirm it contains only the current
   `image_seo_tool` package.
5. Test the wheel in a clean Python environment with `pip install
   image_seo_tool-<version>-py3-none-any.whl`, then import the package and
   confirm the translation and public UI assets are included, and start the
   hosted and public app factories. Test the repo-root local launcher separately.
6. Commit the release, tag it with `v<version>`, and push the commit and tag.
   Publish the distribution only after its target registry and credentials are
   chosen.

Keep the core dependency set small. FastAPI, multipart parsing, and Uvicorn
belong to the optional `web` install; HTTP test dependencies belong to `dev`.
