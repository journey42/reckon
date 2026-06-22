"""Slug helpers for debate pages."""

import re
from typing import Callable


def slugify(text: str) -> str:
    """Lowercase, alphanumerics joined by single hyphens; fallback 'debate'."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "debate"


def unique_slug(base: str, exists: Callable[[str], bool]) -> str:
    """Return base, or base-2/base-3/... until exists(candidate) is False."""
    if not exists(base):
        return base
    n = 2
    while exists(f"{base}-{n}"):
        n += 1
    return f"{base}-{n}"
