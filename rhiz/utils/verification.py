"""Email-verification token helpers for group-origin signups."""

import secrets
from datetime import datetime, timezone

from sqlmodel import select

from rhiz.state.base import User

TOKEN_TTL_HOURS = 72


def generate_token() -> str:
    """Return a URL-safe, unguessable verification token."""
    return secrets.token_urlsafe(32)


def is_group_origin(nxt: str | None) -> bool:
    """True if a signup's `next` points at a group page."""
    return bool(nxt) and nxt.startswith("/group/")


def verify_and_enable(session, token: str) -> "User | None":
    """Enable the account owning a valid, unexpired token (single-use).

    Returns the User on success, or None if the token is empty, unknown, or
    expired.
    """
    if not token:
        return None
    user = session.exec(
        select(User).where(User.verification_token == token)
    ).first()
    if user is None:
        return None
    expires = user.verification_expires_at
    if expires is None or expires < datetime.now(timezone.utc).replace(tzinfo=None):
        return None
    user.enabled = True
    user.verification_token = None
    user.verification_expires_at = None
    session.add(user)
    session.commit()
    return user
