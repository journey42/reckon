"""Password-reset flow fixes (client report: "the email works, but the
password reset seems to be broken").

Three defects are covered here:
  * the emailed link pointed at the apex domain, which 404s on every deep
    path, so the reset page was unreachable from the email;
  * the temporary password was committed *before* the send, so a failed or
    undelivered email left the account holding a password nobody received
    (rollback cannot undo a commit);
  * the temporary password alphabet included ``&``, ``<`` and ``>``, which
    HTML mail clients mangle — a copied password then failed to match.
"""

import os
import re

import pytest
from sqlmodel import select

from rhiz.state.base import User
from rhiz.utils import comms
from rhiz.utils.security import hash_password, verify_password

_DB_URL = os.environ.get("DB_URL", "")
_HOST = (re.search(r"@([^/?]+)", _DB_URL) or [None, ""])[1] if _DB_URL else ""
_IS_LOCAL = _HOST.startswith("localhost") or _HOST.startswith("127.0.0.1")
_DB_ENABLED = os.environ.get("RHIZ_DB_TESTS") == "1" and _IS_LOCAL

requires_db = pytest.mark.skipif(
    not _DB_ENABLED, reason="set RHIZ_DB_TESTS=1 and a local DB_URL"
)


class _FakePoller:
    def __init__(self, status):
        self._status = status

    def result(self):
        return {"status": self._status}


class _FakeEmailClient:
    """Stands in for azure.communication.email.EmailClient."""

    def __init__(self, status="Succeeded", raises=False):
        self.status = status
        self.raises = raises
        self.sent = []

    @classmethod
    def from_connection_string(cls, conn):
        return cls._instance

    def begin_send(self, message):
        self.sent.append(message)
        if self.raises:
            raise RuntimeError("smtp exploded")
        return _FakePoller(self.status)


@pytest.fixture()
def fake_mailbox(monkeypatch):
    inst = _FakeEmailClient()
    _FakeEmailClient._instance = inst
    monkeypatch.setattr(comms, "EmailClient", _FakeEmailClient)
    return inst


class TestTempPasswordCharset:
    def test_length(self):
        assert len(comms.generate_temp_password()) == 12

    def test_no_html_significant_characters(self):
        """& < > " ' get entity-encoded or swallowed inside HTML email, so a
        password copied out of the message stops matching the stored one."""
        for _ in range(500):
            pw = comms.generate_temp_password()
            assert not set(pw) & set("&<>\"'!@#$%^*()"), pw

    def test_alphanumeric_only(self):
        for _ in range(200):
            assert comms.generate_temp_password().isalnum()


@requires_db
class TestResetEmailPersistence:
    @pytest.fixture()
    def session(self):
        import reflex as rx

        with rx.session() as s:
            yield s

    @pytest.fixture()
    def user(self, session):
        from datetime import datetime, timezone

        suffix = datetime.utcnow().strftime("%H%M%S%f")
        original = hash_password("Original_pass1")
        u = User(
            username=f"pwreset_{suffix}",
            email=f"pwreset_{suffix}@test.local",
            password=original,
            enabled=True,
            role=0,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        yield u, original
        fresh = session.get(User, u.id)
        if fresh is not None:
            session.delete(fresh)
        session.commit()

    def _stored_hash(self, user_id):
        import reflex as rx

        with rx.session() as s:
            return s.get(User, user_id).password

    def test_successful_send_persists_new_password(
        self, session, user, fake_mailbox
    ):
        u, original = user
        assert comms.send_password_reset_email(
            session, u, "https://www.rhiz.ai/reset_password_via_email"
        ) is True
        stored = self._stored_hash(u.id)
        assert stored != original
        # The emailed password must verify against what was stored.
        emailed = re.search(
            r"temporary password is: (\S+)", fake_mailbox.sent[0]["content"]["plainText"]
        ).group(1)
        ok, _ = verify_password(emailed, stored)
        assert ok is True

    def test_failed_send_does_not_change_the_password(
        self, session, user, fake_mailbox
    ):
        """A rejected send must not leave the account on an unsent password."""
        u, original = user
        fake_mailbox.status = "Failed"
        assert (
            comms.send_password_reset_email(
                session, u, "https://www.rhiz.ai/reset_password_via_email"
            )
            is False
        )
        assert self._stored_hash(u.id) == original

    def test_send_exception_does_not_change_the_password(
        self, session, user, fake_mailbox
    ):
        u, original = user
        fake_mailbox.raises = True
        with pytest.raises(RuntimeError):
            comms.send_password_reset_email(
                session, u, "https://www.rhiz.ai/reset_password_via_email"
            )
        assert self._stored_hash(u.id) == original

    def test_email_carries_username_and_canonical_link(
        self, session, user, fake_mailbox
    ):
        """The reset page asks for the username, so the mail must name it, and
        the link must be the canonical host (the apex 404s on deep paths)."""
        u, _ = user
        url = "https://www.rhiz.ai/reset_password_via_email"
        comms.send_password_reset_email(session, u, url)
        msg = fake_mailbox.sent[0]["content"]
        assert u.username in msg["plainText"]
        assert url in msg["plainText"]
        assert url in msg["html"]


class TestNoHardcodedApexLink:
    def test_auth_state_uses_public_base_url(self):
        """The apex host only redirects '/'; every deep path 404s there, which
        is what made the emailed reset link dead."""
        source = open(
            os.path.join(
                os.path.dirname(__file__), "..", "rhiz", "state", "auth.py"
            ),
            encoding="utf-8",
        ).read()
        assert "send_password_reset_email(" in source
        assert '"https://rhiz.ai/reset_password_via_email"' not in source
        # The origin comes from the shared helper, which reads PUBLIC_BASE_URL.
        assert "public_origin()" in source
