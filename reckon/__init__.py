"""Reckon package initialization."""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Populate os.environ from a local .env file if present.

    We only set variables that are not already defined in the environment so
    explicit exports take precedence. Keeps dependency footprint minimal.
    """

    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


_load_dotenv()
