"""Outbound email (Azure Communication Services).

Three rules this module exists to enforce:

* The sending credential comes from the ``AZURE_COMMUNICATION_CONNECTION_STRING``
  container secret. It used to be a literal here, which meant anyone with repo
  read access could mail anyone as ``DoNotReply@rhiz.ai``.
* A dev box must not be able to send real mail by accident: ``MAIL_DRY_RUN=1``
  prints the message to the log instead of handing it to ACS.
* Anything interpolated into the HTML part is entity-escaped, and a password is
  only persisted *after* ACS accepts the send.
"""

import os
import secrets
import string
from datetime import datetime, timezone
from html import escape

import reflex as rx
from azure.communication.email import EmailClient

from rhiz.state.base import User  # models live where the session gets them
from rhiz.utils.security import hash_password

CONNECTION_STRING_ENV = "AZURE_COMMUNICATION_CONNECTION_STRING"

SUPPORT_EMAIL_ADDRESS = "DoNotReply@rhiz.ai"

# Alphanumeric only. The old alphabet included ``& < > " ' ! @ # $ % ^ * ( )``,
# which HTML mail entity-encodes or drops, so a temporary password copied out
# of the message no longer matched the stored hash.
_TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits


def generate_temp_password(length: int = 12) -> str:
    """A random, mail-safe, URL-safe temporary password."""
    return "".join(
        secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(length)
    )


class _ConsolePoller:
    """Stands in for the ACS send poller in dry-run mode."""

    def __init__(self, message: dict):
        self._message = message

    def result(self) -> dict:
        return {"status": "Succeeded"}


class _ConsoleEmailClient:
    """MAIL_DRY_RUN sink: logs instead of sending.

    Same surface as ``EmailClient`` for what we use it (``begin_send`` returning
    something with ``.result()``), so the senders below never branch on mode.
    """

    def __init__(self):
        self.sent: list[dict] = []

    def begin_send(self, message: dict) -> _ConsolePoller:
        self.sent.append(message)
        content = message.get("content", {})
        to = (message.get("recipients", {}).get("to") or [{}])[0].get("address", "?")
        print(
            f"[MAIL DRY RUN] to={to} subject={content.get('subject', '')!r} "
            f"from={message.get('senderAddress')}"
        )
        for line in (content.get("plainText") or "").splitlines():
            print(f"[MAIL DRY RUN]   {line}")
        return _ConsolePoller(message)


def _mail_dry_run() -> bool:
    """True when mail should be printed rather than sent."""
    return os.environ.get("MAIL_DRY_RUN", "").strip() == "1"


def _email_client():
    """Build the mail client from the container secret (never from the repo)."""
    if _mail_dry_run():
        return _ConsoleEmailClient()
    connection_string = os.environ.get(CONNECTION_STRING_ENV, "").strip()
    if not connection_string:
        raise RuntimeError(
            f"{CONNECTION_STRING_ENV} is not set, so no mail can be sent. Set it "
            "to the Azure Communication Services connection string (container "
            "secret), or set MAIL_DRY_RUN=1 to print mail to the log instead."
        )
    return EmailClient.from_connection_string(connection_string)


def _send(client, message: dict, session=None) -> bool:
    """Hand a message to ACS. Returns True only if ACS accepted it.

    A transport failure re-raises after rolling back ``session`` (when given),
    so a caller that staged a change cannot have it persisted by a later commit.
    """
    try:
        poller = client.begin_send(message)
        result = poller.result()
    except Exception:
        if session is not None:
            session.rollback()
        raise
    return result.get("status") == "Succeeded"


def send_password_reset_email(session: rx.session, user: User, reset_page_url: str):
    """Email a temporary password. The new password is stored only once ACS has
    accepted the send: a failed send must not leave the account sitting on a
    password that was never delivered (and a rollback cannot undo a commit).

    The reset page asks for a username, so the mail names it too.
    """
    temp_password = generate_temp_password()
    username = user.username or user.email
    message = {
        "content": {
            "subject": "Password Reset Request",
            "plainText": (
                f"Hello {username},\n\n"
                f"Your temporary password is: {temp_password}\n"
                f"Log in with your username ({username}) and this password, "
                "then change it immediately.\n"
                f"You can reset your password here: {reset_page_url}"
            ),
            "html": (
                f"<p>Hello {escape(username)},</p>"
                f"<p>Your temporary password is: <strong>{escape(temp_password)}</strong></p>"
                "<p>Log in with your username "
                f"(<strong>{escape(username)}</strong>) and this password, then "
                "change it immediately.</p>"
                f"<p>You can reset your password by clicking "
                f"<a href=\"{escape(reset_page_url, quote=True)}\">here</a>.</p>"
            ),
        },
        "recipients": {"to": [{"address": user.email}]},
        "senderAddress": SUPPORT_EMAIL_ADDRESS,
    }

    if not _send(_email_client(), message):
        return False

    user.password = hash_password(temp_password)
    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    return True


def send_welcome_email(
    session: rx.session, username: str, email: str, beta_site_url: str
):
    """Welcome mail for an account that has just been granted beta access."""
    message = {
        "content": {
            "subject": "Welcome to the Rhiz Beta!",
            # Plain text carries the username and the URL verbatim.
            "plainText": (
                f"Hello {username},\n\n"
                "You have been granted access to the Rhiz beta! You can now log "
                "in using your existing credentials.\n\n"
                f"Access the beta site here: {beta_site_url}\n\n"
                "We look forward to your feedback!"
            ),
            # HTML must be entity-encoded, but never rewritten: an escaped URL
            # is still the same URL, a raw ``&`` in an href is not.
            "html": (
                f"<p>Hello <strong>{escape(username)}</strong>,</p>"
                "<p>You have been granted access to the Rhiz beta! You can now "
                "log in using your existing credentials.</p>"
                "<p>Access the beta site "
                f"<a href=\"{escape(beta_site_url, quote=True)}\">here</a>.</p>"
                "<p>We look forward to your feedback!</p>"
            ),
        },
        "recipients": {"to": [{"address": email}]},
        "senderAddress": SUPPORT_EMAIL_ADDRESS,
    }
    return _send(_email_client(), message, session=session)


def send_verification_email(user: User, verify_url: str) -> bool:
    """Email an account-verification link. Returns True if ACS accepted it."""
    message = {
        "content": {
            "subject": "Verify your Rhiz account",
            "plainText": (
                "Welcome to Rhiz! Confirm your email to activate your account "
                f"and join the group:\n{verify_url}\n\n"
                "If you didn't sign up, you can ignore this message."
            ),
            "html": (
                "<p>Welcome to Rhiz! Confirm your email to activate your "
                "account and join the group:</p>"
                f"<p><a href=\"{escape(verify_url, quote=True)}\">Verify my account</a></p>"
                "<p>If you didn't sign up, you can ignore this message.</p>"
            ),
        },
        "recipients": {"to": [{"address": user.email}]},
        "senderAddress": SUPPORT_EMAIL_ADDRESS,
    }
    return _send(_email_client(), message)
