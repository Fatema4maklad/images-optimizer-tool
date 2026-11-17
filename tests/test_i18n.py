"""The two browser interfaces share complete English/Arabic UI copy."""

import html
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
TRANSLATIONS = ROOT / "src" / "image_seo_tool" / "i18n" / "strings.js"


def test_both_interfaces_have_a_language_switch_and_translated_static_copy():
    translations = TRANSLATIONS.read_text(encoding="utf-8")
    keys = set(re.findall(r'^  "([^"]+)":', translations, re.MULTILINE))
    for page in (ROOT / "web" / "index.html", ROOT / "src" / "image_seo_tool" / "public_web" / "index.html"):
        markup = page.read_text(encoding="utf-8")
        assert 'data-interface-language="en"' in markup
        assert 'data-interface-language="ar"' in markup
        assert '/i18n/strings.js' in markup
        marked = {html.unescape(value) for value in re.findall(r'data-i18n(?:-placeholder|-aria|-title)?="([^"]+)"', markup)}
        assert marked <= keys, f"Missing Arabic translations for {marked - keys} in {page.name}"


def test_language_switch_updates_direction_and_translates_interpolated_text():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the browser-language smoke test.")
    script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const values = new Map();
const context = {
  window: {},
  navigator: { language: 'en-US' },
  localStorage: { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) },
  document: {
    documentElement: { lang: 'en', dir: 'ltr' },
    querySelectorAll: () => [],
    dispatchEvent: () => {},
  },
  CustomEvent: class { constructor(name) { this.name = name; } },
};
vm.runInNewContext(source, context);
if (context.document.documentElement.lang !== 'ar') throw new Error('Arabic is not the first-run language');
context.window.imageSeoI18n.setLanguage('ar');
if (context.document.documentElement.dir !== 'rtl') throw new Error('Arabic is not RTL');
if (context.window.imageSeoI18n.t('Optimize images') !== 'حسّن الصور') throw new Error('Arabic copy missing');
if (context.window.imageSeoI18n.t('Remove {name}', { name: 'test.png' }) !== 'إزالة test.png') throw new Error('Interpolation failed');
if (context.window.imageSeoI18n.userMessage('Use JPEG, PNG, or WebP images.', 'Could not process these images.') !== 'استخدم صور JPEG أو PNG أو WebP.') throw new Error('Known API error remains English');
if (context.window.imageSeoI18n.userMessage('Unexpected server error', 'Could not process these images.') !== 'تعذّرت معالجة هذه الصور.') throw new Error('Unknown API error remains English');
context.window.imageSeoI18n.setLanguage('en');
if (context.document.documentElement.dir !== 'ltr') throw new Error('English is not LTR');
if (context.window.imageSeoI18n.t('Optimize images') !== 'Optimize images') throw new Error('English copy missing');
"""
    result = subprocess.run([node, "-e", script, str(TRANSLATIONS)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
