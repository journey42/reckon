"""Re-sending a verification link, and the guard rails around it.

Before this existed, a lost verification email was a dead end: the account
could not log in and could not be re-created because the username was taken.
Re-sending is easy to get wrong in two specific ways, and both are covered
here — an account that is waiting for *approval* must not be able to approve
itself, and re-sending must not become an unbounded mail cannon.
"""

import os
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from rhiz.state.base import Log, User
from rhiz.utils.security import hash_password
from rhiz.utils.urls import public_origin
from rhiz.utils.verification import (
    IGNORED,
    RESEND_LIMIT,
    RESEND_LOG_TYPE,
    RESEND_WINDOW_MINUTES,
    SENT,
    SEND_FAILED,
    TOO_SOON,
    resend_verification_link,
    stamp_verification_token,
    utcnow_naive,
    verify_and_enable,
)

_DB_URL = os.environ.get("DB_URL", "")
_HOST = (re.search(r"@([^/?]+)", _DB_URL) or [None, ""])[1] if _DB_URL else ""
_DB_ENABLED = os.environ.get("RHIZ_DB_TESTS") == "1" and (
    _HOST.startswith("localhost") or _HOST.startswith("127.0.0.1")
)
requires_db = pytest.mark.skipif(
    not _DB_ENABLED, reason="set RHIZ_DB_TESTS=1 and a local DB_URL"
)


class RecordingSender:
    """Stands in for comms.send_verification_email."""

    def __init__(self, ok=True, raises=False):
        self.ok = ok
        self.raises = raises
        self.sent = []

    def __call__(self, user, url):
        self.sent.append((user.username, url))
        if self.raises:
            raise RuntimeError("acs unreachable")
        return self.ok


@pytest.fixture()
def session():
    if not _DB_ENABLED:
        pytest.skip("database tests disabled")
    import reflex as rx

    with rx.session() as s:
        yield s


@pytest.fixture()
def make_user(session):
    """Create throwaway accounts and remove them (with their logs) after."""
    created = []

    def _make(*, username, enabled=False, with_token=True):
        suffix = datetime.utcnow().strftime("%H%M%S%f")
        u = User(
            email=f"{username}_{suffix}@test.local",
            username=f"{username}_{suffix}",
            password=hash_password("Resend_pass123"),
            enabled=enabled,
            role=0,
            created_at=utcnow_naive(),
            updated_at=utcnow_naive(),
        )
        if with_token:
            stamp_verification_token(u)
        session.add(u)
        session.commit()
        session.refresh(u)
        created.append(u)
        return u

    yield _make

    import reflex as rx

    with rx.session() as s:
        for u in created:
            for log in s.exec(select(Log).where(Log.user_id == u.id)).all():
                s.delete(log)
            s.commit()
            fresh = s.get(User, u.id)
            if fresh is not None:
                fresh.verification_token = None
                s.delete(fresh)
        s.commit()


@requires_db
class TestResendVerificationLink:
    def test_account_awaiting_verification_gets_a_fresh_link(
        self, session, make_user
    ):
        u = make_user(username="waiting")
        original = u.verification_token
        sender = RecordingSender()

        outcome = resend_verification_link(
            session, u.username, base_url="https://www.rhiz.ai", sender=sender
        )
        assert outcome == SENT
        assert len(sender.sent) == 1
        sent_url = sender.sent[0][1]
        assert sender.sent[0][0] == u.username

        import reflex as rx

        with rx.session() as check:
            fresh = check.get(User, u.id)
            assert fresh.verification_token != original  # rotated
            assert fresh.verification_token in sent_url
            assert fresh.enabled is False  # sending does not enable

    def test_the_previous_link_stops_working(self, session, make_user):
        u = make_user(username="retire")
        old_token = u.verification_token
        resend_verification_link(
            session,
            u.username,
            base_url="https://www.rhiz.ai",
            sender=RecordingSender(),
        )
        # The clicked-old-link path must no longer resolve to anybody.
        assert verify_and_enable(session, old_token) is None
        import reflex as rx

        with rx.session() as check:
            assert check.get(User, u.id).enabled is False

    def test_an_account_awaiting_approval_cannot_approve_itself(
        self, session, make_user
    ):
        """Clicking a verification link enables the account, so handing a fresh
        link to an account that is waiting for an administrator would let
        anyone self-approve. Only accounts already holding a token qualify."""
        u = make_user(username="pending", enabled=False, with_token=False)
        sender = RecordingSender()

        outcome = resend_verification_link(
            session, u.username, base_url="https://www.rhiz.ai", sender=sender
        )
        assert outcome == IGNORED
        assert sender.sent == []

        import reflex as rx

        with rx.session() as check:
            fresh = check.get(User, u.id)
            assert fresh.verification_token is None
            assert fresh.enabled is False

    def test_unknown_username_sends_nothing_and_says_nothing_specific(
        self, session, make_user
    ):
        sender = RecordingSender()
        outcome = resend_verification_link(
            session,
            "no-such-user-anywhere",
            base_url="https://www.rhiz.ai",
            sender=sender,
        )
        assert outcome == IGNORED
        assert sender.sent == []

    def test_enabled_account_is_left_alone(self, session, make_user):
        u = make_user(username="active", enabled=True, with_token=True)
        sender = RecordingSender()
        outcome = resend_verification_link(
            session, u.username, base_url="https://www.rhiz.ai", sender=sender
        )
        assert outcome == IGNORED
        assert sender.sent == []

    def test_links_are_capped_per_account(self, session, make_user):
        u = make_user(username="caps")
        for _ in range(RESEND_LIMIT):
            assert (
                resend_verification_link(
                    session,
                    u.username,
                    base_url="https://www.rhiz.ai",
                    sender=RecordingSender(),
                )
                == SENT
            )
        assert (
            resend_verification_link(
                session,
                u.username,
                base_url="https://www.rhiz.ai",
                sender=RecordingSender(),
            )
            == TOO_SOON
        )

    def test_the_cap_slides_after_the_window(self, session, make_user):
        u = make_user(username="slide")
        for _ in range(RESEND_LIMIT):
            resend_verification_link(
                session,
                u.username,
                base_url="https://www.rhiz.ai",
                sender=RecordingSender(),
            )
        # Age the recorded sends past the window; the account may ask again.
        backdated = utcnow_naive() - timedelta(minutes=RESEND_WINDOW_MINUTES + 5)
        for log in session.exec(
            select(Log).where(Log.user_id == u.id, Log.type == RESEND_LOG_TYPE)
        ).all():
            log.created_at = backdated
            session.add(log)
        session.commit()

        assert (
            resend_verification_link(
                session,
                u.username,
                base_url="https://www.rhiz.ai",
                sender=RecordingSender(),
            )
            == SENT
        )

    def test_sends_are_recorded_for_the_cap(self, session, make_user):
        u = make_user(username="audit")
        resend_verification_link(
            session, u.username, base_url="https://www.rhiz.ai", sender=RecordingSender()
        )
        logs = session.exec(
            select(Log).where(Log.user_id == u.id, Log.type == RESEND_LOG_TYPE)
        ).all()
        assert len(logs) == 1

    def test_a_failed_send_does_not_destroy_the_working_link(
        self, session, make_user
    ):
        u = make_user(username="retry")
        original = u.verification_token
        assert (
            resend_verification_link(
                session,
                u.username,
                base_url="https://www.rhiz.ai",
                sender=RecordingSender(raises=True),
            )
            == SEND_FAILED
        )
        import reflex as rx

        with rx.session() as check:
            assert check.get(User, u.id).verification_token == original

        # And the old link still verifies.
        assert verify_and_enable(session, original) is not None

    def test_link_uses_the_canonical_origin_and_keeps_the_group_path(
        self, session, make_user
    ):
        u = make_user(username="origin")
        sender = RecordingSender()
        resend_verification_link(
            session,
            u.username,
            base_url="https://www.rhiz.ai/",
            sender=sender,
            next_path="/group/deep-thoughts",
        )
        to, url = sender.sent[0]
        assert url.startswith("https://www.rhiz.ai/verify_email/")  # no double slash
        # Same convention as the signup link: slashes stay readable, and
        # /login validates the value with safe_next_path before using it.
        assert url.endswith("?next=/group/deep-thoughts")

    def test_default_base_is_the_public_origin(self, session, make_user):
        u = make_user(username="defaults")
        sender = RecordingSender()
        resend_verification_link(session, u.username, sender=sender)
        assert sender.sent[0][1].startswith(public_origin() + "/verify_email/")
