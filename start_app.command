#!/bin/bash

set -u
cd "$(dirname "$0")" || exit 1

fail() {
    echo
    echo "Could not start Image SEO Optimizer."
    echo "$1"
    echo
    read -r -p "Press Return to close..."
    exit 1
}

if ! command -v python3 >/dev/null 2>&1; then
    open "https://www.python.org/downloads/macos/"
    fail "Install Python 3.11 or newer, then double-click this file again."
fi

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    open "https://www.python.org/downloads/macos/"
    fail "Python 3.11 or newer is required. Install the latest Python, then try again."
fi

MAC_ENV=".venv-mac"
MAC_PYTHON="$MAC_ENV/bin/python"

if [ ! -x "$MAC_PYTHON" ]; then
    echo "First-time setup: preparing the app..."
    python3 -m venv "$MAC_ENV" || fail "The Python environment could not be created."
    "$MAC_PYTHON" -m pip install --upgrade pip || fail "pip could not be updated. Check the internet connection."
fi

if ! "$MAC_PYTHON" -c 'from importlib.metadata import version; version("image-seo-tool"); import image_seo_tool, fastapi, uvicorn' >/dev/null 2>&1; then
    echo "Updating the Image SEO Optimizer environment..."
    "$MAC_PYTHON" -m pip install -e ".[web]" || fail "The app dependencies could not be installed. Check the internet connection."
fi

(sleep 2; open "http://127.0.0.1:8765/?app=image-seo-mac") &
echo "Image SEO Optimizer is running. Keep this window open."
echo "Close this window when you are finished."
exec "$MAC_PYTHON" -m uvicorn app:app --host 127.0.0.1 --port 8765
