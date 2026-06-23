"""Email-verification token helpers for debate-origin signups."""

import secrets

TOKEN_TTL_HOURS = 72


def generate_token() -> str:
    """Return a URL-safe, unguessable verification token."""
    return secrets.token_urlsafe(32)


def is_debate_origin(nxt: str | None) -> bool:
    """True if a signup's `next` points at a debate page."""
    return bool(nxt) and nxt.startswith("/debate/")
