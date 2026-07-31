"""Persistent login sessions backed by a cookie token.

Reflex stores ``AppState.user`` in server-side state. That state is lost when
the backend restarts, when the state manager evicts the entry, or when the
browser presents a new client token — and the user is silently bounced to
``/login`` mid-task. These helpers let us rebuild the logged-in user from an
opaque token stored in a cookie, so losing state is no longer a logout.

Security notes
--------------
* Only the SHA-256 hash of the token is persisted. A database leak therefore
  does not yield usable session tokens.
* Tokens are 256 bits of ``secrets`` entropy.
* Expiry slides forward as the session is used, throttled to one write per
  ``REFRESH_THROTTLE`` to avoid a write on every page load.
* Rotating the token on privilege-relevant events (password change) limits the
  damage of a stolen cookie.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import select

from rhiz.state.base import User, UserSession

# How long a session stays valid without being used.
SESSION_TTL = timedelta(days=30)

# Only push ``expires_at``/``last_used_at`` forward at most this often.
REFRESH_THROTTLE = timedelta(hours=12)

COOKIE_NAME = "rhiz_auth"


def _hash_token(token: str) -> str:
    """Hash a raw token for storage/lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(session, user_id: int) -> str:
    """Mint a new session for ``user_id`` and return the raw token.

    The raw token is returned to be placed in a cookie; only its hash is saved.
    """
    raw_token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    session.add(
        UserSession(
            token_hash=_hash_token(raw_token),
            user_id=user_id,
            created_at=now,
            last_used_at=now,
            expires_at=now + SESSION_TTL,
            revoked=False,
        )
    )
    session.commit()
    return raw_token


def resolve_session(session, token: str) -> Optional[User]:
    """Return the ``User`` for a valid token, else ``None``.

    Refreshes the sliding expiry (throttled). Expired or revoked sessions
    return ``None`` so the caller can clear the cookie.
    """
    if not token:
        return None

    # The returned User is used after this session closes, so it must not be
    # expired on commit below. Without this, the sliding-expiry commit expires
    # the instance and the caller hits DetachedInstanceError on first attribute
    # access - which only reproduces once a session is older than
    # REFRESH_THROTTLE, making it look intermittent.
    session.expire_on_commit = False

    row = session.exec(
        select(UserSession).where(UserSession.token_hash == _hash_token(token))
    ).first()
    if row is None or row.revoked:
        return None

    now = datetime.utcnow()
    if row.expires_at <= now:
        return None

    user = session.exec(select(User).where(User.id == row.user_id)).first()
    if user is None or not user.enabled:
        return None

    # Slide the window forward, but avoid writing on every single request.
    if now - row.last_used_at > REFRESH_THROTTLE:
        row.last_used_at = now
        row.expires_at = now + SESSION_TTL
        session.add(row)
        session.commit()

    return user


def revoke_session(session, token: str) -> bool:
    """Revoke a single session by raw token. True if a row was revoked."""
    if not token:
        return False
    row = session.exec(
        select(UserSession).where(UserSession.token_hash == _hash_token(token))
    ).first()
    if row is None:
        return False
    row.revoked = True
    session.add(row)
    session.commit()
    return True


def revoke_all_for_user(session, user_id: int) -> int:
    """Revoke every active session for a user. Returns the count revoked.

    Used when an account is disabled or its password changes, so existing
    cookies elsewhere stop working.
    """
    rows = session.exec(
        select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked == False,  # noqa: E712 - SQL comparison
        )
    ).all()
    for row in rows:
        row.revoked = True
        session.add(row)
    if rows:
        session.commit()
    return len(rows)


def purge_expired(session) -> int:
    """Delete expired/revoked rows. Safe to call periodically."""
    now = datetime.utcnow()
    rows = session.exec(
        select(UserSession).where(
            (UserSession.expires_at <= now) | (UserSession.revoked == True)  # noqa: E712
        )
    ).all()
    for row in rows:
        session.delete(row)
    if rows:
        session.commit()
    return len(rows)
