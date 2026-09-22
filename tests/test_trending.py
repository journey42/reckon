"""Trending pages must actually execute their queries.

The ranking-selector rework (sort_label + _apply_trending_order) broke the
trending pages in production with a plain argument-count TypeError: the
ordering helper kept a leftover `self` after being converted from a mixin
method to a module function. Compile-time checks (frontend export) and the
non-DB test tier cannot catch that — only executing the query can.
"""

import os
import re
from datetime import datetime, timezone

import pytest
from sqlmodel import delete as sqlmodel_delete
from sqlmodel import select

from rhiz.pages import reckonings
from rhiz.state.base import Group, Reckoning, ReckoningTypes, User

_DB_URL = os.environ.get("DB_URL", "")
_HOST = (re.search(r"@([^/?]+)", _DB_URL) or [None, ""])[1] if _DB_URL else ""
_IS_LOCAL = _HOST.startswith("localhost") or _HOST.startswith("127.0.0.1")
_DB_ENABLED = os.environ.get("RHIZ_DB_TESTS") == "1" and _IS_LOCAL

requires_db = pytest.mark.skipif(
    not _DB_ENABLED,
    reason="set RHIZ_DB_TESTS=1 and a local DB_URL to run trending query tests",
)

TRENDING_STATES = [
    reckonings.TrendingConceptsByUpvotesPageState,
    reckonings.TrendingConceptsBySupportPageState,
]

TEST_SLUG = "trending-test-group"
TEST_FOUNDING = "trending test founding question"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _purge(session) -> None:
    """Remove any rows left by earlier failed runs (FK-safe order).

    SQL-level deletes because the models define no relationships, so the
    ORM's unit of work cannot order these deletes itself.
    """
    session.exec(
        sqlmodel_delete(Reckoning).where(
            Reckoning.group_id.in_(
                select(Group.id).where(Group.slug == TEST_SLUG)
            )
        )
    )
    session.exec(sqlmodel_delete(Group).where(Group.slug == TEST_SLUG))
    session.exec(
        sqlmodel_delete(Reckoning).where(Reckoning.content == TEST_FOUNDING)
    )
    session.commit()


@pytest.fixture(scope="module")
def session_factory():
    if not _DB_ENABLED:
        pytest.skip("trending database tests disabled")
    import reflex as rx

    return rx.session


@pytest.fixture()
def session(session_factory):
    with session_factory() as s:
        yield s


@requires_db
class TestTrendingQueriesExecute:
    def test_both_trending_pages_query_all_rankings(self, session):
        """Every ranking option must produce an executable query on both
        trending pages — this runs the SQL the page runs on load."""
        import reflex as rx

        for state_cls in TRENDING_STATES:
            state = state_cls()
            for label in reckonings.TRENDING_SORT_OPTIONS:
                state.sort_label = label
                with rx.session() as s:
                    query = state._window_query(s)
                    rows = s.exec(query).all()
                # Executing without error is the point; result shape is
                # (Reckoning, upvote_count, support_count) per the select.
                assert isinstance(rows, list)

    def test_ranking_orders_as_selected(self, session):
        """With mixed support counts the ordering reflects the selection."""
        import reflex as rx

        _purge(session)

        user = session.exec(select(User).where(User.id == 1)).first()
        created_user = False
        if user is None:
            from rhiz.utils.security import hash_password

            user = User(
                username="trending-tester",
                email="trending-tester@test.local",
                password=hash_password("Test_pass123"),
                enabled=True,
                created_at=_utcnow(),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            created_user = True
        uid = user.id

        founding = Reckoning(
            content=TEST_FOUNDING,
            type=ReckoningTypes.concept,
            created_at=_utcnow(),
            updated_at=_utcnow(),
            user_id=uid,
        )
        session.add(founding)
        session.commit()
        session.refresh(founding)
        group = Group(
            name=TEST_SLUG,
            slug=TEST_SLUG,
            concept_id=founding.id,
            founding_question="q",
            is_public=True,
            created_by=uid,
            created_at=_utcnow(),
        )
        session.add(group)
        session.commit()
        session.refresh(group)
        ids = []
        try:
            for i, content in enumerate(
                ["zero-support concept", "loved concept"]
            ):
                c = Reckoning(
                    content=content,
                    type=ReckoningTypes.concept,
                    group_id=group.id,
                    created_at=_utcnow(),
                    updated_at=_utcnow(),
                    user_id=uid,
                )
                session.add(c)
                session.commit()
                session.refresh(c)
                ids.append(c.id)
                if i == 1:
                    for _ in range(3):
                        session.add(
                            Reckoning(
                                content="",
                                type=ReckoningTypes.up_vote,
                                parent_reckoning_id=c.id,
                                user_id=uid,
                                group_id=group.id,
                                created_at=_utcnow(),
                                updated_at=_utcnow(),
                            )
                        )
                    session.commit()
            state = reckonings.TrendingConceptsByUpvotesPageState()
            state.sort_label = "Most upvotes"
            with rx.session() as s:
                rows = s.exec(state._window_query(s)).all()
            content_order = [r[0].content for r in rows if r[0].id in ids]
            assert content_order[0] == "loved concept"
        finally:
            _purge(session)
            if created_user:
                u = session.get(User, uid)
                if u is not None:
                    session.delete(u)
                session.commit()