"""URL helpers shared by auth redirects."""

from urllib.parse import urlparse, unquote


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
