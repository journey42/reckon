"""Convener comment-hiding (client request): the record stays, content is
masked as "Hidden by group convener" for everyone but the convener, and only
the convener (or an admin) can hide/unhide."""

import os
import re
from datetime import datetime, timezone

import pytest
from sqlmodel import select

from rhiz.state.base import Group, Reckoning, ReckoningTypes, User
from rhiz.utils.moderation import can_moderate, hide_comment, unhide_comment

_DB_URL = os.environ.get("DB_URL", "")
_HOST = (re.search(r"@([^/?]+)", _DB_URL) or [None, ""])[1] if _DB_URL else ""
_IS_LOCAL = _HOST.startswith("localhost") or _HOST.startswith("127.0.0.1")
_DB_ENABLED = os.environ.get("RHIZ_DB_TESTS") == "1" and _IS_LOCAL

requires_db = pytest.mark.skipif(
    not _DB_ENABLED, reason="set RHIZ_DB_TESTS=1 and a local DB_URL"
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(scope="module")
def session_factory():
    if not _DB_ENABLED:
        pytest.skip("moderation database tests disabled")
    import reflex as rx

    return rx.session


@pytest.fixture()
def session(session_factory):
    with session_factory() as s:
        yield s


@pytest.fixture()
def _people(session):
    """Convener, member, admin — created once, cleaned up per test."""
    from rhiz.utils.security import hash_password

    suffix = datetime.utcnow().strftime("%H%M%S%f")
    people = {}
    for role, name in ((0, "conv"), (0, "member"), (2, "admin")):
        u = User(
            username=f"modtest_{name}_{suffix}",
            email=f"modtest_{name}_{suffix}@test.local",
            password=hash_password("Test_pass123"),
            enabled=True,
            role=role,
            created_at=_utcnow(),
        )
        session.add(u)
        people[name] = u
    session.commit()
    for u in people.values():
        session.refresh(u)
    yield people
    for u in people.values():
        fresh = session.get(User, u.id)
        if fresh is not None:
            session.delete(fresh)
    session.commit()


@pytest.fixture()
def _group_and_comment(session, _people):
    from rhiz.utils.security import hash_password

    rid = session.exec(select(Reckoning.id)).first()
    founding = Reckoning(
        content=f"modtest founding {rid}",
        type=ReckoningTypes.concept,
        created_at=_utcnow(),
        updated_at=_utcnow(),
        user_id=_people["conv"].id,
    )
    session.add(founding)
    session.commit()
    session.refresh(founding)
    group = Group(
        slug=f"modtest-{datetime.utcnow().strftime('%H%M%S%f')}",
        concept_id=founding.id,
        name="modtest group",
        is_public=True,
        created_by=_people["conv"].id,
        created_at=_utcnow(),
    )
    session.add(group)
    session.commit()
    session.refresh(group)
    comment = Reckoning(
        content="a comment the convener may want to hide",
        type=ReckoningTypes.support,
        parent_reckoning_id=founding.id,
        group_id=group.id,
        created_at=_utcnow(),
        updated_at=_utcnow(),
        user_id=_people["member"].id,
    )
    session.add(comment)
    session.commit()
    session.refresh(comment)
    yield group, comment
    c = session.get(Reckoning, comment.id)
    if c is not None:
        session.delete(c)
    g = session.get(Group, group.id)
    if g is not None:
        session.delete(g)
    f = session.get(Reckoning, founding.id)
    if f is not None:
        session.delete(f)
    session.commit()


@requires_db
class TestConvenerHiding:
    def test_convener_can_hide_and_unhide(self, session, _people, _group_and_comment):
        group, comment = _group_and_comment
        assert can_moderate(_people["conv"], group) is True
        assert hide_comment(session, comment.id, _people["conv"]) is True
        session.refresh(comment)
        assert comment.hidden_by_convener is True
        assert comment.hidden_by == _people["conv"].id
        # Record kept: content is still there (privacy of the group already
        # limits visibility; the mask is presentational).
        assert comment.content == "a comment the convener may want to hide"
        assert unhide_comment(session, comment.id, _people["conv"]) is True
        session.refresh(comment)
        assert comment.hidden_by_convener is False

    def test_member_cannot_hide(self, session, _people, _group_and_comment):
        group, comment = _group_and_comment
        assert can_moderate(_people["member"], group) is False
        assert hide_comment(session, comment.id, _people["member"]) is False
        session.refresh(comment)
        assert comment.hidden_by_convener is False

    def test_admin_can_hide(self, session, _people, _group_and_comment):
        group, comment = _group_and_comment
        assert can_moderate(_people["admin"], group) is True
        assert hide_comment(session, comment.id, _people["admin"]) is True
        session.refresh(comment)
        assert comment.hidden_by_convener is True

    def test_hide_is_audit_logged(self, session, _people, _group_and_comment):
        group, comment = _group_and_comment
        hide_comment(session, comment.id, _people["conv"])
        from rhiz.state.base import Log

        row = session.exec(
            select(Log)
            .where(Log.type == "group_moderation")
            .order_by(Log.id.desc())
        ).first()
        assert row is not None
        assert f"hid comment {comment.id}" in row.content

    def test_hidden_comment_can_still_be_unhidden_by_convener_only(
        self, session, _people, _group_and_comment
    ):
        group, comment = _group_and_comment
        hide_comment(session, comment.id, _people["conv"])
        # Member can't unhide either.
        assert unhide_comment(session, comment.id, _people["member"]) is False
        session.refresh(comment)
        assert comment.hidden_by_convener is True

@requires_db
class TestConceptHiding:
    def test_creator_can_hide_concept(self, session, _people, _group_and_comment):
        from rhiz.utils.moderation import hide_comment as hide  # works for concepts too

        group, comment = _group_and_comment
        # Create a concept inside the group
        concept = Reckoning(
            content="a concept the creator may hide",
            type=ReckoningTypes.concept,
            group_id=group.id,
            created_at=_utcnow(),
            updated_at=_utcnow(),
            user_id=_people["member"].id,
        )
        session.add(concept)
        session.commit()
        session.refresh(concept)
        try:
            assert hide(session, concept.id, _people["conv"]) is True
            session.refresh(concept)
            assert concept.hidden_by_convener is True
            # Member cannot unhide
            assert unhide_comment(session, concept.id, _people["member"]) is False
            # Creator restores
            assert unhide_comment(session, concept.id, _people["conv"]) is True
            session.refresh(concept)
            assert concept.hidden_by_convener is False
        finally:
            c = session.get(Reckoning, concept.id)
            if c is not None:
                session.delete(c)
            session.commit()
