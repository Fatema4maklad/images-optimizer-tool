"""Short-lived, disk-backed ZIP downloads for the hosted API."""

from __future__ import annotations

import re
import secrets
import time
from pathlib import Path


TOKEN_PATTERN = re.compile(r"[0-9a-f]{32}\Z")


class DownloadStore:
    def __init__(self, root: Path, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError("Download lifetime must be positive.")
        self.root = Path(root)
        self.ttl_seconds = ttl_seconds
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.cleanup()

    def create(self, data: bytes) -> str:
        self.cleanup()
        token = secrets.token_hex(16)
        path = self.root / f"{token}.zip"
        try:
            with path.open("xb") as output:
                output.write(data)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return token

    def get(self, token: str) -> Path | None:
        if not TOKEN_PATTERN.fullmatch(token):
            return None
        self.cleanup()
        path = self.root / f"{token}.zip"
        return path if path.is_file() else None

    def cleanup(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        for path in self.root.glob("*.zip"):
            if not TOKEN_PATTERN.fullmatch(path.stem):
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except FileNotFoundError:
                continue
