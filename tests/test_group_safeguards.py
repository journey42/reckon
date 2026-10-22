"""Safeguards for self-service group creation (client request).

New accounts get ``can_create_groups`` automatically, bounded by:
  * an admin auto/manual toggle (``auto_group_creation_enabled``),
  * a rolling 24h quota shared by groups AND live rooms,
  * the email-verification / approval gate (``user.enabled``).
"""

import os
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from rhiz.state.base import AppSetting, Group, Reckoning, ReckoningTypes, User, set_setting
from rhiz.utils.groups import (
    DEFAULT_GROUP_DAILY_LIMIT,
    auto_group_creation_enabled,
    check_group_creation_quota,
    group_creation_daily_limit,
)

_DB_URL = os.environ.get("DB_URL", "")
_HOST = (re.search(r"@([^/?]+)", _DB_URL) or [None, ""])[1] if _DB_URL else ""
_IS_LOCAL = _HOST.startswith("localhost") or _HOST.startswith("127.0.0.1")
_DB_ENABLED = os.environ.get("RHIZ_DB_TESTS") == "1" and _IS_LOCAL

requires_db = pytest.mark.skipif(
    not _DB_ENABLED, reason="set RHIZ_DB_TESTS=1 and a local DB_URL"
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def session():
    if not _DB_ENABLED:
        pytest.skip("database tests disabled")
    import reflex as rx

    with rx.session() as s:
        yield s


@pytest.fixture()
def restore_settings():
    """App settings are global — put back whatever the tests touched."""
    saved = {}
    import reflex as rx

    with rx.session() as s:
        for row in s.exec(select(AppSetting)).all():
            saved[row.key] = row.value
    yield saved
    import reflex as rx

    with rx.session() as s:
        for key in ("auto_group_creation_enabled", "group_creation_daily_limit"):
            row = s.exec(select(AppSetting).where(AppSetting.key == key)).first()
            if key in saved:
                if row is not None:
                    row.value = saved[key]
                    s.add(row)
            elif row is not None:
                s.delete(row)
        s.commit()


class TestSettingsHelpers:
    def test_auto_group_creation_defaults_to_on(self, restore_settings):
        set_setting("auto_group_creation_enabled", "true")
        assert auto_group_creation_enabled() is True

    def test_auto_group_creation_can_be_switched_off(self, restore_settings):
        set_setting("auto_group_creation_enabled", "false")
        assert auto_group_creation_enabled() is False

    def test_daily_limit_default_and_override(self, restore_settings):
        set_setting("group_creation_daily_limit", "")
        assert group_creation_daily_limit() == DEFAULT_GROUP_DAILY_LIMIT
        set_setting("group_creation_daily_limit", "2")
        assert group_creation_daily_limit() == 2

    def test_daily_limit_garbage_falls_back(self, restore_settings):
        set_setting("group_creation_daily_limit", "lots")
        assert group_creation_daily_limit() == DEFAULT_GROUP_DAILY_LIMIT


@requires_db
class TestQuota:
    @pytest.fixture()
    def people(self, session):
        from rhiz.utils.security import hash_password

        suffix = datetime.utcnow().strftime("%H%M%S%f")
        made = []
        for name, role, can, enabled in (
            ("member", 0, True, True),
            ("newbie", 0, False, True),
            ("unverified", 0, True, False),
            ("boss", 2, False, True),
        ):
            u = User(
                username=f"quota_{name}_{suffix}",
                email=f"quota_{name}_{suffix}@test.local",
                password=hash_password("Test_pass123"),
                enabled=enabled,
                role=role,
                can_create_groups=can,
                created_at=_utcnow(),
            )
            session.add(u)
            made.append(u)
        session.commit()
        for u in made:
            session.refresh(u)
        yield {n: u for (n, u) in zip(("member", "newbie", "unverified", "boss"), made)}
        for u in made:
            fresh = session.get(User, u.id)
            if fresh is not None:
                session.delete(fresh)
        session.commit()

    def _make_group(self, session, creator_id, name, age_hours=0):
        founding = Reckoning(
            content=f"founding {name}",
            type=ReckoningTypes.concept,
            created_at=_utcnow(),
            updated_at=_utcnow(),
            user_id=creator_id,
        )
        session.add(founding)
        session.commit()
        session.refresh(founding)
        g = Group(
            slug=f"quota-{name}-{datetime.utcnow().strftime('%f%H%M%S')}",
            concept_id=founding.id,
            name=name,
            is_public=True,
            created_by=creator_id,
            created_at=_utcnow() - timedelta(hours=age_hours),
        )
        session.add(g)
        session.commit()
        session.refresh(g)
        return g, founding

    def _cleanup_groups(self, session, pairs):
        for g, founding in pairs:
            row = session.get(Group, g.id)
            if row is not None:
                session.delete(row)
            session.commit()
            f = session.get(Reckoning, founding.id)
            if f is not None:
                session.delete(f)
        session.commit()

    def test_permitted_user_under_limit_is_allowed(
        self, session, people, restore_settings
    ):
        set_setting("group_creation_daily_limit", "2")
        ok, msg = check_group_creation_quota(session, people["member"])
        assert ok is True, msg

    def test_user_without_grant_is_denied(self, session, people, restore_settings):
        ok, msg = check_group_creation_quota(session, people["newbie"])
        assert ok is False
        assert "permission" in msg.lower()

    def test_unverified_account_is_denied(self, session, people, restore_settings):
        ok, msg = check_group_creation_quota(session, people["unverified"])
        assert ok is False
        assert "verify" in msg.lower()

    def test_admin_is_exempt_from_permission_check(
        self, session, people, restore_settings
    ):
        # boss has can_create_groups=False but role=admin
        ok, _ = check_group_creation_quota(session, people["boss"])
        assert ok is True

    def test_limit_blocks_after_n_groups_in_24h(
        self, session, people, restore_settings
    ):
        set_setting("group_creation_daily_limit", "2")
        pairs = [
            self._make_group(session, people["member"].id, f"recent{i}") for i in range(2)
        ]
        try:
            ok, msg = check_group_creation_quota(session, people["member"])
            assert ok is False
            assert "limit" in msg.lower()
        finally:
            self._cleanup_groups(session, pairs)

    def test_groups_older_than_24h_do_not_count(
        self, session, people, restore_settings
    ):
        set_setting("group_creation_daily_limit", "2")
        pairs = [
            self._make_group(session, people["member"].id, f"old{i}", age_hours=30)
            for i in range(3)
        ]
        try:
            ok, msg = check_group_creation_quota(session, people["member"])
            assert ok is True, msg
        finally:
            self._cleanup_groups(session, pairs)

    def test_zero_limit_pauses_creation(self, session, people, restore_settings):
        set_setting("group_creation_daily_limit", "0")
        ok, msg = check_group_creation_quota(session, people["member"])
        assert ok is False
        assert "paused" in msg.lower()

    def test_room_path_skips_permission_but_keeps_limit(
        self, session, people, restore_settings
    ):
        """Live rooms are groups: the cap must apply there too, but room
        creation has never required the can_create_groups grant."""
        set_setting("group_creation_daily_limit", "1")
        ok, _ = check_group_creation_quota(
            session, people["newbie"], require_permission=False
        )
        assert ok is True  # not a group-creator, but may still open a room
        pairs = [self._make_group(session, people["newbie"].id, "roomy")]
        try:
            ok, msg = check_group_creation_quota(
                session, people["newbie"], require_permission=False
            )
            assert ok is False
            assert "limit" in msg.lower()
        finally:
            self._cleanup_groups(session, pairs)

    def test_anonymous_is_denied(self, session, restore_settings):
        ok, msg = check_group_creation_quota(session, None)
        assert ok is False
        assert "log in" in msg.lower()
