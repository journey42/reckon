"""Every emailed link must point at the canonical host and survive HTML mail.

The password-reset mail was hardcoded to https://rhiz.ai, whose apex only
redirects "/" — every deep path 404s, so the link looked broken to anyone
clicking it from their inbox. The account-verification mail was already built
from PUBLIC_BASE_URL; these tests keep it that way and cover the two other
emailed links (welcome) plus the token the verification link carries.
"""

import os
import re

import pytest

from rhiz.utils import comms
from rhiz.utils.verification import TOKEN_TTL_HOURS, generate_token, is_group_origin

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

MAIL_MODULES = [
    os.path.join("rhiz", "utils", "comms.py"),
    os.path.join("rhiz", "state", "auth.py"),
    os.path.join("rhiz", "pages", "users.py"),
    os.path.join("rhiz", "pages", "resend_verification.py"),
]

# A quoted apex URL is the bug; prose mentioning it in a comment is fine.
QUOTED_APEX = re.compile(r"""["']https?://rhiz\.ai""")


def _read(rel_path: str) -> str:
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as fh:
        return fh.read()


class TestEmailedLinkHosts:
    @pytest.mark.parametrize("rel_path", MAIL_MODULES)
    def test_no_quoted_apex_url(self, rel_path):
        assert not QUOTED_APEX.search(_read(rel_path)), (
            f"{rel_path} builds a URL from the apex host, which 404s on every "
            "deep path; use PUBLIC_BASE_URL (https://www.rhiz.ai in prod)"
        )

    def test_welcome_link_uses_the_canonical_origin(self):
        src = _read(os.path.join("rhiz", "pages", "users.py"))
        assert "public_base_url()" in src

    def test_verification_link_uses_the_canonical_origin(self):
        src = _read(os.path.join("rhiz", "state", "auth.py"))
        assert "verify_email/" in src
        assert "public_origin()" in src
        # ...and that helper is the one place that reads the setting.
        helpers = _read(os.path.join("rhiz", "utils", "urls.py"))
        assert "PUBLIC_BASE_URL" in helpers

    def test_shared_origin_helper_reads_the_env(self):
        from rhiz.pages.group_common import public_base_url

        saved = os.environ.get("PUBLIC_BASE_URL")
        try:
            os.environ["PUBLIC_BASE_URL"] = "https://www.rhiz.ai/"
            assert public_base_url() == "https://www.rhiz.ai"  # trailing slash gone
            os.environ.pop("PUBLIC_BASE_URL")
            assert public_base_url() == "http://localhost:3000"
        finally:
            # Leave the process environment exactly as the runner set it.
            if saved is None:
                os.environ.pop("PUBLIC_BASE_URL", None)
            else:
                os.environ["PUBLIC_BASE_URL"] = saved


class _FakePoller:
    def __init__(self, status):
        self._status = status

    def result(self):
        return {"status": self._status}


class _FakeEmailClient:
    def __init__(self, status="Succeeded"):
        self.status = status
        self.sent = []

    @classmethod
    def from_connection_string(cls, conn):
        return cls._instance

    def begin_send(self, message):
        self.sent.append(message)
        return _FakePoller(self.status)


@pytest.fixture()
def fake_mailbox(monkeypatch):
    inst = _FakeEmailClient()
    _FakeEmailClient._instance = inst
    monkeypatch.setattr(comms, "EmailClient", _FakeEmailClient)
    return inst


class _StubSession:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


class TestWelcomeEmail:
    def test_link_survives_html_without_being_mangled(self, fake_mailbox):
        comms.send_welcome_email(
            _StubSession(),
            "ada&co",
            "ada@example.com",
            "https://www.rhiz.ai/login?next=/group/x&src=email",
        )
        msg = fake_mailbox.sent[0]["content"]
        # Plain text must carry the address verbatim.
        assert "https://www.rhiz.ai/login?next=/group/x&src=email" in msg["plainText"]
        # HTML must entity-encode, not swallow, the ampersands.
        assert "ada&amp;co" in msg["html"]
        assert "next=/group/x&amp;src=email" in msg["html"]

    def test_returns_false_when_acs_rejects(self, fake_mailbox):
        fake_mailbox.status = "Failed"
        assert (
            comms.send_welcome_email(
                _StubSession(), "ada", "ada@example.com", "https://www.rhiz.ai"
            )
            is False
        )

    def test_send_failure_rolls_back(self, monkeypatch):
        class Boom(_FakeEmailClient):
            @classmethod
            def from_connection_string(cls, conn):
                return cls._instance

            def begin_send(self, message):
                raise RuntimeError("acs down")

        Boom._instance = Boom()
        monkeypatch.setattr(comms, "EmailClient", Boom)
        s = _StubSession()
        with pytest.raises(RuntimeError):
            comms.send_welcome_email(s, "ada", "ada@example.com", "https://www.rhiz.ai")
        assert s.rolled_back is True


class TestVerificationToken:
    def test_urlsafe_so_the_link_cannot_break(self):
        """The token travels inside an <a href>, so anything outside base64url
        would need escaping (and ``+``/``/``/``&`` mangle in HTML mail)."""
        for _ in range(500):
            tok = generate_token()
            assert re.fullmatch(r"[A-Za-z0-9_-]+", tok), tok
            assert not set(tok) & set("&<>\"'+/=")

    def test_tokens_are_unique(self):
        assert len({generate_token() for _ in range(200)}) == 200

    def test_ttl_is_a_whole_number_of_days_at_least(self):
        assert TOKEN_TTL_HOURS >= 24

    def test_group_origin_detection(self):
        assert is_group_origin("/group/some-slug") is True
        assert is_group_origin("/") is False
        assert is_group_origin(None) is False


_DB_URL = os.environ.get("DB_URL", "")
_HOST = (re.search(r"@([^/?]+)", _DB_URL) or [None, ""])[1] if _DB_URL else ""
_DB_ENABLED = os.environ.get("RHIZ_DB_TESTS") == "1" and (
    _HOST.startswith("localhost") or _HOST.startswith("127.0.0.1")
)
requires_db = pytest.mark.skipif(
    not _DB_ENABLED, reason="set RHIZ_DB_TESTS=1 and a local DB_URL"
)


@requires_db
class TestVerifyAndEnable:
    """What the verification link does when it is clicked."""

    @pytest.fixture()
    def session(self):
        import reflex as rx

        with rx.session() as s:
            yield s

    @pytest.fixture()
    def account(self, session):
        from datetime import datetime, timedelta, timezone

        from rhiz.state.base import User
        from rhiz.utils.security import hash_password

        suffix = datetime.utcnow().strftime("%H%M%S%f")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        u = User(
            email=f"verify_{suffix}@test.local",
            username=f"verify{suffix[-9:]}",
            password=hash_password("Verify_pass123"),
            enabled=False,
            role=0,
            created_at=now,
            updated_at=now,
            verification_token=generate_token(),
            verification_expires_at=now + timedelta(hours=TOKEN_TTL_HOURS),
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        yield u
        fresh = session.get(User, u.id)
        if fresh is not None:
            fresh.verification_token = None
            session.delete(fresh)
        session.commit()

    def test_valid_token_enables_the_account(self, session, account):
        from rhiz.utils.verification import verify_and_enable

        token = account.verification_token
        found = verify_and_enable(session, token)
        assert found is not None and found.id == account.id
        import reflex as rx

        with rx.session() as check:
            u = check.get(type(account), account.id)
            assert u.enabled is True
            assert u.verification_token is None  # single-use

    def test_expired_token_is_refused(self, session, account):
        from datetime import datetime, timedelta, timezone

        from rhiz.state.base import User
        from rhiz.utils.verification import verify_and_enable

        account.verification_expires_at = (
            datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        )
        session.add(account)
        session.commit()
        assert verify_and_enable(session, account.verification_token) is None
        import reflex as rx

        with rx.session() as check:
            assert check.get(User, account.id).enabled is False

    def test_replay_is_refused(self, session, account):
        from rhiz.utils.verification import verify_and_enable

        token = account.verification_token
        assert verify_and_enable(session, token) is not None
        assert verify_and_enable(session, token) is None

    def test_empty_and_unknown_tokens_are_refused(self, session, account):
        from rhiz.utils.verification import verify_and_enable

        assert verify_and_enable(session, "") is None
        assert verify_and_enable(session, "not-a-real-token") is None


class TestSendingCredential:
    """The ACS connection string must not live in the repo.

    It used to be a literal in rhiz/utils/comms.py, so the sending key was in
    git: anyone with repo read access could mail anyone as DoNotReply@rhiz.ai.
    It now comes from the AZURE_COMMUNICATION_CONNECTION_STRING container
    secret, and the key that was committed has to be rotated regardless,
    because it stays in git history.
    """

    def test_no_connection_string_literal_in_the_source(self):
        src = _read(os.path.join("rhiz", "utils", "comms.py"))
        assert "accesskey=" not in src.lower()
        assert "CONNECTION_STRING_ENV" in src

    def test_missing_credential_fails_loudly(self, monkeypatch):
        monkeypatch.delenv(comms.CONNECTION_STRING_ENV, raising=False)
        monkeypatch.delenv("MAIL_DRY_RUN", raising=False)
        with pytest.raises(RuntimeError) as exc:
            comms._email_client()
        assert comms.CONNECTION_STRING_ENV in str(exc.value)

    def test_credential_is_read_from_the_environment(self, monkeypatch):
        sentinel = "endpoint=https://example.invalid/;accesskey=placeholder"
        monkeypatch.setenv(comms.CONNECTION_STRING_ENV, sentinel)
        monkeypatch.delenv("MAIL_DRY_RUN", raising=False)
        seen = {}

        class Fake:
            @classmethod
            def from_connection_string(cls, value):
                seen["value"] = value
                return "client"

        monkeypatch.setattr(comms, "EmailClient", Fake)
        assert comms._email_client() == "client"
        assert seen["value"] == sentinel

    def test_dry_run_never_touches_the_network(self, monkeypatch, capsys):
        """A dev box must not be able to send real mail by accident."""
        monkeypatch.delenv(comms.CONNECTION_STRING_ENV, raising=False)
        monkeypatch.setenv("MAIL_DRY_RUN", "1")
        assert comms._mail_dry_run() is True
        assert isinstance(comms._email_client(), comms._ConsoleEmailClient)

        class Boom:
            @classmethod
            def from_connection_string(cls, value):  # pragma: no cover
                raise AssertionError("dry run must not build an ACS client")

        monkeypatch.setattr(comms, "EmailClient", Boom)
        assert (
            comms.send_verification_email(
                _StubUser("someone@example.com"), "https://www.rhiz.ai/verify_email/abc"
            )
            is True
        )
        out = capsys.readouterr().out
        assert "[MAIL DRY RUN]" in out and "someone@example.com" in out


class _StubUser:
    def __init__(self, email):
        self.email = email


class TestResendEntryPoints:
    """A recovery path nobody can find is not a recovery path."""

    def test_page_is_registered(self):
        assert "resend_verification" in _read(
            os.path.join("rhiz", "pages", "__init__.py")
        )

    def test_login_offers_it(self):
        assert "/resend_verification" in _read(os.path.join("rhiz", "pages", "login.py"))

    def test_verify_sent_page_offers_it(self):
        assert "/resend_verification" in _read(
            os.path.join("rhiz", "pages", "verify_email_sent.py")
        )

    def test_form_routes_through_the_shared_util(self):
        src = _read(os.path.join("rhiz", "pages", "resend_verification.py"))
        assert "resend_verification_link" in src
        assert "public_origin" in src
