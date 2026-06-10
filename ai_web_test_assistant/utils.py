"""Shared utility helpers for the AI Web Test Assistant demo."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def normalize_url(raw_url: str) -> str:
    """Return a URL with a scheme so Playwright can navigate to it."""
    url = raw_url.strip()
    if not url:
        raise ValueError("URL cannot be empty.")

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("Please enter a valid URL.")

    return url


def safe_filename(value: str) -> str:
    """Convert display text into a filesystem-safe filename segment."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    return cleaned.strip("-") or "screenshot"


def timestamp() -> str:
    """Return a compact timestamp for grouping screenshot runs."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_directory(path: str | Path) -> Path:
    """Create a directory if needed and return it as a Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory

