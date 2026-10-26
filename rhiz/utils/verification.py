"""Email-verification token helpers for group-origin signups."""

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlmodel import select

from rhiz.state.base import Log, User
from rhiz.utils.urls import public_origin

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
    user = session.exec(select(User).where(User.verification_token == token)).first()
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


# --- re-sending a verification link -----------------------------------------

# Outcomes of resend_verification_link(). They are strings rather than bools so
# the page can distinguish "we mailed it" from "we deliberately said nothing",
# without the page having to know why.
SENT = "sent"
TOO_SOON = "too_soon"
IGNORED = "ignored"
SEND_FAILED = "send_failed"

RESEND_LOG_TYPE = "verification_resend"
RESEND_LIMIT = 3
RESEND_WINDOW_MINUTES = 60


def utcnow_naive() -> datetime:
    """Naive UTC, matching how the models stamp created_at."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def stamp_verification_token(user: User) -> str:
    """Give ``user`` a fresh single-use token and expiry. Does not commit."""
    token = generate_token()
    user.verification_token = token
    user.verification_expires_at = utcnow_naive() + timedelta(hours=TOKEN_TTL_HOURS)
    return token


def _default_sender():
    """The real mailer, imported lazily so callers that inject a sender (tests,
    scripts) never need the Azure mail SDK installed."""
    from rhiz.utils.comms import send_verification_email

    return send_verification_email


def _recent_sends(session, user_id: int) -> int:
    """Sends recorded for this account inside the rolling window."""
    since = utcnow_naive() - timedelta(minutes=RESEND_WINDOW_MINUTES)
    return len(
        session.exec(
            select(Log).where(
                Log.user_id == user_id,
                Log.type == RESEND_LOG_TYPE,
                Log.created_at > since,
            )
        ).all()
    )


def resend_verification_link(
    session,
    username: str,
    base_url: str | None = None,
    sender=None,
    next_path: str | None = None,
) -> str:
    """Re-send a verification link to the account named by ``username``.

    Returns one of SENT / TOO_SOON / IGNORED / SEND_FAILED. The caller shows the
    same message to the user whatever comes back, so none of these outcomes may
    reveal whether the account exists.

    Guard rails, in order:
      * an account with no token is waiting for an *administrator*, and clicking
        a verification link enables an account, so re-sending one would let
        anyone self-approve; those are IGNORED;
      * already-enabled accounts have nothing to verify;
      * at most RESEND_LIMIT sends per RESEND_WINDOW_MINUTES per account, so a
        lost email cannot become a mail cannon.

    The token is rotated *before* the send but rolled back if the send fails, so
    a flaky mail provider cannot destroy a link that was still working.
    """
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or user.enabled or not user.verification_token:
        return IGNORED
    if _recent_sends(session, user.id) >= RESEND_LIMIT:
        return TOO_SOON

    base = (base_url or public_origin()).rstrip("/")
    send = sender or _default_sender()

    token = stamp_verification_token(user)  # not committed yet, deliberately
    url = f"{base}/verify_email/{token}"
    if next_path:
        # Slashes stay readable, matching the signup link; /login validates the
        # value with safe_next_path before using it.
        url = f"{url}?next={quote(next_path, safe='/')}"

    try:
        accepted = bool(send(user, url))
    except Exception:
        session.rollback()
        return SEND_FAILED
    if not accepted:
        session.rollback()
        return SEND_FAILED

    session.add(user)
    session.add(
        Log(
            user_id=user.id,
            type=RESEND_LOG_TYPE,
            content=f"verification link re-sent to {user.email}",
            created_at=utcnow_naive(),
        )
    )
    session.commit()
    return SENT
