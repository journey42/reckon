"""URL helpers shared by auth redirects and outbound links."""

import os
from urllib.parse import urlparse, unquote


def public_origin() -> str:
    """Canonical origin for anything leaving the app (email links, QR codes,
    share URLs). Set PUBLIC_BASE_URL in production (e.g. https://www.rhiz.ai);
    defaults to the local dev frontend. Trailing slash is stripped.

    This is the single source of truth: never build an outbound URL from a
    hardcoded domain, or the link 404s wherever the app is actually served.
    """
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:3000").rstrip("/")


def safe_next_path(nxt: str | None) -> str | None:
    """Return `nxt` if it is a safe same-origin relative path, else None.

    Decodes percent-encoding and backslashes before validating (browsers do
    so before navigating), then requires no scheme, no netloc, a leading '/',
    and not a protocol-relative '//'.
    """
    if not nxt:
        return None
    normalized = unquote(nxt).replace("\\", "/")
    parsed = urlparse(normalized)
    if (
        not parsed.scheme
        and not parsed.netloc
        and normalized.startswith("/")
        and not normalized.startswith("//")
    ):
        return nxt
    return None
