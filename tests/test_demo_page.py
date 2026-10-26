"""Tests for the permanent Q&A behind /demo, and for the group page's question.

Two lanes, matching the rest of this suite:

* the data layer — what makes a question permanent, which one ``/demo`` shows,
  how many answers it puts on the first screen — runs with ``RHIZ_DB_TESTS=1``
  and a local ``DB_URL``;
* the page itself needs a running app, so it also waits for
  ``RHIZ_BROWSER_TEST=1`` and ``RHIZ_BASE`` (same convention as
  ``test_room_outbox.py``).
"""

from __future__ import annotations

import datetime
import os
import time
import uuid

import pytest
import reflex as rx
from sqlmodel import select

from rhiz.state.base import (
    AppSetting,
    Group,
    Reckoning,
    RoomParticipant,
    RoomSwap,
    User,
)
from rhiz.utils import demo
from rhiz.utils.rooms import (
    close_room,
    create_room,
    extend_room,
    get_or_create_participant,
    reopen_room,
    submit_answer,
    swap_support,
)

BASE = os.environ.get("RHIZ_BASE", "http://localhost:3000")

# These tests create and delete rooms and users. Running them against a remote
# database is how a test suite destroys production data, so mirror the guard in
# tests/test_room_outbox.py: enabled only when DB_URL points at localhost.
from urllib.parse import urlparse

_db_host = (urlparse(os.environ.get("DB_URL", "")).hostname or "").lower()
_IS_LOCAL = _db_host.startswith("localhost") or _db_host.startswith("127.0.0.1")
_DB_ENABLED = os.environ.get("RHIZ_DB_TESTS") == "1" and _IS_LOCAL

needs_db = pytest.mark.skipif(
    not _DB_ENABLED,
    reason="set RHIZ_DB_TESTS=1 and a DB_URL on localhost/127.0.0.1",
)
needs_browser = pytest.mark.skipif(
    not os.environ.get("RHIZ_BROWSER_TEST"),
    reason="set RHIZ_BROWSER_TEST=1 with a running app at RHIZ_BASE",
)


# --------------------------------------------------------------------------
# helpers and fixtures
# --------------------------------------------------------------------------
def _purge(session, room: Group) -> None:
    """Delete a question and everything under it.

    This goes through the same helpers the admin panel uses — ``delete_room``
    for a Q&A, ``delete_group`` for a group — rather than a hand-rolled cascade:
    the ``group.concept_id`` / ``reckoning.group_id`` cycle is fiddly, both
    helpers already solve it in one transaction, and teardown should not be the
    place where a second, weaker version of that logic is invented.
    """
    from rhiz.utils.groups import delete_group
    from rhiz.utils.rooms import delete_room

    if room.is_room:
        assert delete_room(session, room.id)
    else:
        delete_group(session, room.id)


def _room(session, slug: str) -> Group:
    room = session.exec(select(Group).where(Group.slug == slug)).first()
    assert room is not None, f"no room with slug {slug!r}"
    return room


@pytest.fixture()
def organiser():
    """One throwaway account to own the questions under test."""
    from rhiz.utils.security import hash_password

    with rx.session() as session:
        user = session.exec(
            select(User).where(User.username == "demo_organiser")
        ).first()
        if user is None:
            user = User(
                username="demo_organiser",
                email="demo_organiser@test.local",
                password=hash_password("Test_pass123"),
                enabled=True,
                role=2,
                can_create_groups=True,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        return user.id


@pytest.fixture()
def demo_question(organiser):
    """A permanent question, restored out of /demo's way afterwards."""
    question = f"A demo question asked only in tests [{uuid.uuid4().hex[:8]}]"
    with rx.session() as session:
        previous = demo.read_active_slug(session)
        room = demo.create_demo_question(session, question, organiser)
        slug = room.slug
    yield slug, question
    with rx.session() as session:
        _purge(session, _room(session, slug))
        if previous:
            demo.write_active_slug(session, previous)


@pytest.fixture()
def no_pointer_yet():
    """Pretend /demo has never been configured, then put it back afterwards.

    Creating a question only claims /demo when nothing is pointing at anything;
    an organiser adding a question for a *new* audience must not silently move
    the printed address, so that case needs its own clean starting point.
    """
    with rx.session() as session:
        previous = demo.read_active_slug(session)
        row = session.exec(
            select(AppSetting).where(AppSetting.key == demo.DEMO_ROOM_SETTING)
        ).first()
        if row is not None:
            session.delete(row)
            session.commit()
    yield
    with rx.session() as session:
        if previous:
            demo.write_active_slug(session, previous)


def answer_as(slug: str, text: str, token: str | None = None) -> int:
    """One anonymous answer, submitted the way the page submits one."""
    token = token or f"device-{uuid.uuid4().hex}"
    with rx.session() as session:
        room = _room(session, slug)
        participant = get_or_create_participant(session, room, token)
        answer, _similar = submit_answer(session, room, participant, text)
        return answer.id


def participant_of(slug: str, answer_id: int) -> RoomParticipant:
    with rx.session() as session:
        room = _room(session, slug)
        for row in session.exec(
            select(RoomParticipant).where(RoomParticipant.room_id == room.id)
        ).all():
            if row.current_answer_id == answer_id:
                session.refresh(row)
                return row
    raise AssertionError("no participant holds that answer")


# --------------------------------------------------------------------------
# what makes a question permanent
# --------------------------------------------------------------------------
@needs_db
class TestPermanentQuestions:
    def test_a_permanent_question_has_no_deadline(self, demo_question):
        slug, _ = demo_question
        with rx.session() as session:
            room = _room(session, slug)
            assert room.close_at is None
            assert demo.is_demo_question(room)

    def test_an_ordinary_room_is_not_a_demo_question(self, organiser):
        with rx.session() as session:
            room = create_room(session, f"Timed {uuid.uuid4().hex}", organiser, 30)
            assert room.close_at is not None
            assert not demo.is_demo_question(room)
            _purge(session, room)

    def test_the_deadline_check_leaves_it_open(self, demo_question):
        """``enforce_deadline`` closes rooms on every read; with no deadline it
        must be a no-op, which is what makes "permanent" true rather than
        incidental."""
        from rhiz.utils.rooms import enforce_deadline

        slug, _ = demo_question
        with rx.session() as session:
            room = enforce_deadline(session, _room(session, slug))
            assert room.status == "open"

    def test_a_permanent_question_cannot_be_extended(self, demo_question):
        """Extending treats a missing deadline as "now"; that would give the
        printed /demo question a timer it never had."""
        slug, _ = demo_question
        with rx.session() as session:
            room = _room(session, slug)
            assert extend_room(session, room.id) is None
            session.refresh(room)
            assert room.close_at is None
            assert demo.is_demo_question(room)

    def test_reopening_restores_it_without_a_deadline(self, demo_question):
        """A facilitator closing it by mistake must be able to undo it — and
        undoing it must not convert a permanent question into a timed one."""
        slug, _ = demo_question
        with rx.session() as session:
            room = _room(session, slug)
            assert close_room(session, room.id)
        with rx.session() as session:
            room = reopen_room(session, _room(session, slug).id)
            assert room is not None
            assert room.status == "open"
            assert room.close_at is None
            assert demo.is_demo_question(room)

    def test_it_is_a_room_in_every_other_way(self, demo_question):
        """It reuses the Q&A engine, so it must behave like one: anonymous
        participants, one answer each, consolidation available."""
        slug, _ = demo_question
        first = answer_as(slug, "First wording.", token="device-one")
        second = answer_as(slug, "Second wording.", token="device-two")
        with rx.session() as session:
            room = _room(session, slug)
            supporter = participant_of(slug, second)
            assert swap_support(session, room, supporter, first)
        with rx.session() as session:
            room = _room(session, slug)
            ids = [item["id"] for item in demo.visible_answers(session, room, 5)["items"]]
            assert first in ids
            assert second not in ids, "a withdrawn wording should not be listed"


# --------------------------------------------------------------------------
# which question /demo shows
# --------------------------------------------------------------------------
@needs_db
class TestChoosingTheQuestion:
    def test_the_first_question_becomes_the_one_shown(self, no_pointer_yet, demo_question):
        """With nothing configured, the page should not be empty."""
        slug, _ = demo_question
        with rx.session() as session:
            assert demo.read_active_slug(session) == slug
            assert demo.active_demo_question(session).slug == slug

    def test_adding_a_question_does_not_hijack_a_configured_page(
        self, no_pointer_yet, demo_question, organiser
    ):
        """The printed address has to keep asking what it was already asking."""
        first_slug, _ = demo_question
        with rx.session() as session:
            other = demo.create_demo_question(
                session, f"A question for a later audience [{uuid.uuid4().hex[:8]}]", organiser
            )
            other_slug = other.slug
            assert demo.active_demo_question(session).slug == first_slug
            _purge(session, _room(session, other_slug))

    def test_the_pointer_is_a_single_appsetting_row(self, no_pointer_yet, demo_question):
        slug, _ = demo_question
        with rx.session() as session:
            row = session.exec(
                select(AppSetting).where(AppSetting.key == demo.DEMO_ROOM_SETTING)
            ).first()
            assert row is not None
            assert row.value == slug

    def test_switching_changes_what_the_page_shows(self, organiser, demo_question):
        first_slug, _ = demo_question
        with rx.session() as session:
            second = demo.create_demo_question(
                session, f"A second audience's question [{uuid.uuid4().hex[:8]}]", organiser
            )
            second_slug = second.slug
        try:
            with rx.session() as session:
                assert demo.set_active_demo_question(session, second_slug)
                assert demo.active_demo_question(session).slug == second_slug
            with rx.session() as session:
                assert demo.set_active_demo_question(session, first_slug)
                assert demo.active_demo_question(session).slug == first_slug
        finally:
            with rx.session() as session:
                _purge(session, _room(session, second_slug))

    def test_switching_does_not_disturb_the_answers_it_is_not_showing(
        self, organiser, demo_question
    ):
        """The client wants several audiences, each with its own history."""
        slug, _ = demo_question
        marker = uuid.uuid4().hex[:6]
        answer_as(slug, f"Something said by the first audience {marker}.")
        with rx.session() as session:
            before = demo.visible_answers(session, _room(session, slug), 20)["total"]
        with rx.session() as session:
            other = demo.create_demo_question(
                session, f"A later question [{uuid.uuid4().hex[:8]}]", organiser
            )
            other_slug = other.slug
            demo.set_active_demo_question(session, other_slug)
        try:
            with rx.session() as session:
                after = demo.visible_answers(session, _room(session, slug), 20)["total"]
                assert after == before
                assert demo.active_demo_question(session).slug == other_slug
        finally:
            with rx.session() as session:
                _purge(session, _room(session, other_slug))

    def test_a_timed_room_cannot_be_sent_to_the_demo_page(self, organiser):
        with rx.session() as session:
            room = create_room(session, f"Not a demo {uuid.uuid4().hex}", organiser, 15)
            assert not demo.set_active_demo_question(session, room.slug)
            _purge(session, room)

    def test_a_closed_question_cannot_be_saved_as_the_demo(self, demo_question):
        """The picker and the public resolver must agree; otherwise "Saved"
        means something visitors never see."""
        slug, _ = demo_question
        with rx.session() as session:
            before = demo.read_active_slug(session)
            room = _room(session, slug)
            close_room(session, room.id)
            assert demo.set_active_demo_question(session, slug) is False
            assert demo.read_active_slug(session) == before
            assert demo.demo_question_by_slug(session, slug, require_open=True) is None
            row = next(
                r for r in demo.list_demo_questions(session) if r["slug"] == slug
            )
            assert row["closed"] is True

    def test_a_broken_pointer_falls_back_rather_than_showing_nothing(
        self, demo_question
    ):
        """A printed card cannot be corrected after the fact, so the page has to
        land on *a* question even when the pointer outlives its row."""
        slug, _ = demo_question
        with rx.session() as session:
            demo.write_active_slug(session, "no-such-question")
            fallback = demo.active_demo_question(session)
            assert fallback is not None
            assert demo.is_demo_question(fallback)
            demo.write_active_slug(session, slug)

    def test_listing_a_question_tells_the_panel_what_it_needs(
        self, no_pointer_yet, demo_question
    ):
        slug, question = demo_question
        marker = uuid.uuid4().hex[:6]
        answer_as(slug, f"An answer someone left {marker}.")
        with rx.session() as session:
            rows = [r for r in demo.list_demo_questions(session) if r["slug"] == slug]
        assert len(rows) == 1
        row = rows[0]
        assert row["question"] == question
        assert row["answers"] == 1
        assert row["is_active"] is True
        assert row["closed"] is False


# --------------------------------------------------------------------------
# what goes on the first screen
# --------------------------------------------------------------------------
@needs_db
class TestTheFirstScreen:
    def test_only_five_answers_are_listed(self, demo_question):
        slug, _ = demo_question
        for i in range(demo.ANSWERS_ABOVE_THE_FOLD + 3):
            answer_as(slug, f"Distinct answer {i} about {uuid.uuid4().hex}")
        with rx.session() as session:
            page = demo.visible_answers(session, _room(session, slug), 5)
            assert len(page["items"]) == demo.ANSWERS_ABOVE_THE_FOLD
            assert page["has_more"] is True
            assert page["total"] >= demo.ANSWERS_ABOVE_THE_FOLD + 1

    def test_the_supported_answer_ranks_first(self, demo_question):
        slug, _ = demo_question
        backed = answer_as(slug, "A wording two people chose.", token="device-a")
        other = answer_as(slug, f"A wording one person chose. {uuid.uuid4().hex}", "device-b")
        with rx.session() as session:
            room = _room(session, slug)
            swap_support(session, room, participant_of(slug, other), backed)
        with rx.session() as session:
            items = demo.visible_answers(session, _room(session, slug), 10)["items"]
            assert items[0]["id"] == backed
            assert items[0]["support"] >= 2

    def test_the_page_is_told_which_answers_have_support(self, demo_question):
        """``hot`` is decided server-side: a page cannot compare a Reflex item
        var against a number at compile time."""
        slug, _ = demo_question
        answer_as(slug, "An answer with no support.")
        with rx.session() as session:
            items = demo.visible_answers(session, _room(session, slug), 5)["items"]
            assert items
            assert all(isinstance(item["hot"], bool) for item in items)

    def test_a_question_nobody_has_answered_is_not_an_error(self, demo_question):
        slug, _ = demo_question
        with rx.session() as session:
            page = demo.visible_answers(session, _room(session, slug), 5)
            assert page["items"] == []
            assert page["total"] == 0
            assert page["has_more"] is False

    def test_the_demo_copy_is_the_clients_own_words(self):
        """The client supplied both paragraphs; rewording them is not ours."""
        from rhiz.pages.demo import EXPLAIN_ABOVE, EXPLAIN_BELOW

        assert EXPLAIN_ABOVE.startswith(
            "Rhiz helps groups discover what they actually believe."
        )
        assert "theory of emergence" in EXPLAIN_BELOW
        assert EXPLAIN_ABOVE.endswith("it didn't know it had.")
        # asked for as one block above the Q&A and one below, so neither may be
        # split into a list of bullet points
        assert "\n" not in EXPLAIN_ABOVE and "\n" not in EXPLAIN_BELOW


# --------------------------------------------------------------------------
# the group page's founding question (the "not displaying" report)
# --------------------------------------------------------------------------
@needs_db
class TestFoundingQuestionIsNeverBlank:
    def _group(self, question: str) -> str:
        from rhiz.utils.groups import create_group

        with rx.session() as session:
            group = create_group(
                session, f"FG {uuid.uuid4().hex[:6]}", question, _organiser_id()
            )
            return group.slug

    def test_the_concept_is_used_when_the_column_is_empty(self):
        from rhiz.utils.groups import founding_text, get_group_by_slug

        question = f"A question kept only on its concept [{uuid.uuid4().hex[:8]}]"
        slug = self._group(question)
        try:
            with rx.session() as session:
                group = _group_row(session, slug)
                group.founding_question = ""
                session.add(group)
                session.commit()
            with rx.session() as session:
                assert get_group_by_slug(session, slug).founding_question == ""
                assert founding_text(session, _group_row(session, slug)) == question
        finally:
            with rx.session() as session:
                _purge(session, _group_row(session, slug))

    def test_the_column_wins_when_both_are_filled(self):
        """An owner's edit must not be overruled by the older concept."""
        from rhiz.utils.groups import founding_text, get_group_by_slug

        slug = self._group("The original question.")
        try:
            with rx.session() as session:
                group = _group_row(session, slug)
                group.founding_question = "The edited question."
                session.add(group)
                session.commit()
            with rx.session() as session:
                get_group_by_slug(session, slug)
                assert (
                    founding_text(session, _group_row(session, slug))
                    == "The edited question."
                )
        finally:
            with rx.session() as session:
                _purge(session, _group_row(session, slug))

    def test_an_empty_creation_is_rejected(self):
        """A group with no question has nothing to display, and neither the read
        fallback nor the backfill can recover text that was never written."""
        from rhiz.utils.groups import create_group

        with rx.session() as session:
            with pytest.raises(ValueError):
                create_group(
                    session, f"FG0 {uuid.uuid4().hex[:6]}", "   ", _organiser_id()
                )
            session.rollback()

    def test_an_empty_edit_leaves_both_copies_intact(self):
        """The demonstrable cause of the client's blank header: saving the edit
        form with an empty question wrote "" over the column *and* the concept,
        so the fallback had nothing to recover."""
        from rhiz.utils.groups import create_group, founding_text, update_group_details

        question = f"Keep me [{uuid.uuid4().hex[:8]}]"
        with rx.session() as session:
            group = create_group(
                session, f"FG4 {uuid.uuid4().hex[:6]}", question, _organiser_id()
            )
            slug = group.slug
            group_id = group.id
            concept_id = group.concept_id
        try:
            with rx.session() as session:
                with pytest.raises(ValueError):
                    update_group_details(
                        session, group_id, founding_question="   "
                    )
                session.rollback()
            with rx.session() as session:
                group = _group_row(session, slug)
                assert group.founding_question == question
                assert session.get(Reckoning, concept_id).content == question
                assert founding_text(session, group) == question
        finally:
            with rx.session() as session:
                _purge(session, _group_row(session, slug))

    def test_nothing_is_invented_when_neither_side_has_text(self):
        from rhiz.utils.groups import create_group, founding_text

        with rx.session() as session:
            group = create_group(
                session, f"FG3 {uuid.uuid4().hex[:6]}", "Q.", _organiser_id()
            )
            concept_id = group.concept_id
            group.founding_question = ""
            session.add(group)
            session.commit()
            slug = group.slug
        try:
            with rx.session() as session:
                concept = session.get(Reckoning, concept_id)
                concept.content = ""
                session.add(concept)
                session.commit()
                assert founding_text(session, _group_row(session, slug)) == ""
        finally:
            with rx.session() as session:
                _purge(session, _group_row(session, slug))


def _group_row(session, slug: str) -> Group:
    group = session.exec(select(Group).where(Group.slug == slug)).first()
    assert group is not None
    return group


def _organiser_id() -> int:
    with rx.session() as session:
        user = session.exec(select(User).where(User.username == "demo_organiser")).first()
        if user is not None:
            return user.id
    from rhiz.utils.security import hash_password

    with rx.session() as session:
        user = User(
            username="demo_organiser",
            email="demo_organiser@test.local",
            password=hash_password("Test_pass123"),
            enabled=True,
            role=2,
            can_create_groups=True,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


# --------------------------------------------------------------------------
# the page in a browser
# --------------------------------------------------------------------------
@pytest.fixture()
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        launched = playwright.chromium.launch()
        yield launched
        launched.close()


@pytest.fixture()
def shown_question(demo_question):
    """A question that /demo is actually pointing at.

    The page reads one pointer from the database, so a browser test cannot
    assert on a question it merely created — it has to move the pointer first,
    and put it back afterwards.
    """
    slug, question = demo_question
    with rx.session() as session:
        previous = demo.read_active_slug(session)
        demo.write_active_slug(session, slug)
    yield slug, question
    with rx.session() as session:
        if previous:
            demo.write_active_slug(session, previous)


def open_demo(browser):
    page = browser.new_context().new_page()
    page.goto(f"{BASE}/demo", wait_until="networkidle", timeout=90000)
    return page


def body(page) -> str:
    return " ".join(page.inner_text("body").split())


@needs_db
@needs_browser
class TestDemoPageInABrowser:
    def test_it_asks_the_active_question(self, browser, shown_question):
        slug, question = shown_question
        page = open_demo(browser)
        page.wait_for_selector("#rhiz-demo-answer", timeout=45000)
        assert question in body(page)
        page.context.close()

    def test_the_explanation_sits_above_and_below_the_question(
        self, browser, demo_question
    ):
        page = open_demo(browser)
        page.wait_for_selector("#rhiz-demo-answer", timeout=45000)
        text = body(page)
        assert text.index("Rhiz helps groups discover") < text.index("Submit answer")
        assert text.index("theory of emergence") > text.index("Submit answer")
        assert "Sign up" in text, "the client asked for a sign-up link at the top"
        assert "Closes in" not in text, "a demo with a countdown is not a demo"
        page.context.close()

    def test_typed_words_survive_a_refresh(self, browser, shown_question):
        """The page reloads itself every 20 seconds to show arriving answers;
        that must not throw away words someone is still typing."""
        text = f"Words typed but not yet sent [{uuid.uuid4().hex[:6]}]"
        page = open_demo(browser)
        page.wait_for_selector("#rhiz-demo-answer", timeout=45000)
        page.fill("#rhiz-demo-answer", text)
        page.wait_for_timeout(800)
        draft = page.evaluate(
            "() => localStorage.getItem('rhiz_demo_draft_' + "
            "document.getElementById('rhiz-demo-question').value + '_v1')"
        )
        assert draft == text, "the draft was not stored on the device"

        page.reload(wait_until="networkidle")
        page.wait_for_selector("#rhiz-demo-answer", timeout=45000)
        deadline = time.time() + 12
        restored = ""
        while time.time() < deadline:
            restored = page.input_value("#rhiz-demo-answer")
            if restored == text:
                break
            time.sleep(0.4)
        assert restored == text, "a refresh erased what the visitor had typed"
        page.context.close()

    def test_a_stranger_can_answer_without_an_account(self, browser, shown_question):
        slug, _ = shown_question
        text = f"An answer typed by a stranger [{uuid.uuid4().hex[:6]}]"
        page = open_demo(browser)
        page.wait_for_selector("#rhiz-demo-answer", timeout=45000)
        page.fill("#rhiz-demo-answer", text)
        page.click("#rhiz-demo-submit")

        deadline = time.time() + 20
        landed = None
        while time.time() < deadline and landed is None:
            with rx.session() as session:
                landed = session.exec(
                    select(Reckoning).where(Reckoning.content == text)
                ).first()
            time.sleep(0.6)
        assert landed is not None, "the answer never reached the database"
        assert "Your answer" in body(page)
        assert text in body(page), "their own wording is not shown in the list"
        page.context.close()

    def test_five_answers_then_show_more(self, browser, shown_question):
        slug, _ = shown_question
        marker = uuid.uuid4().hex[:6]
        for i in range(demo.ANSWERS_ABOVE_THE_FOLD + 2):
            answer_as(slug, f"Crowd answer number {i} about {marker}")
        page = open_demo(browser)
        page.wait_for_selector("text=What people have said", timeout=45000)

        def on_screen() -> int:
            return page.locator(f"text={marker}").count()

        assert on_screen() <= demo.ANSWERS_ABOVE_THE_FOLD, (
            f"{on_screen()} answers on the first screen; five was the request"
        )
        assert "more answer" in body(page)
        page.click("#rhiz-demo-more")
        deadline = time.time() + 15
        while time.time() < deadline and on_screen() <= demo.ANSWERS_ABOVE_THE_FOLD:
            time.sleep(0.5)
        assert on_screen() > demo.ANSWERS_ABOVE_THE_FOLD, "show more showed nothing"
        page.click("#rhiz-demo-fewer")
        deadline = time.time() + 15
        while time.time() < deadline and on_screen() > demo.ANSWERS_ABOVE_THE_FOLD:
            time.sleep(0.5)
        assert on_screen() <= demo.ANSWERS_ABOVE_THE_FOLD, "the list would not fold up"
        page.context.close()

    def test_a_near_duplicate_taps_into_the_existing_wording(
        self, browser, shown_question
    ):
        """The consolidation the explainer describes, demonstrated on the page
        whose job is to demonstrate it."""
        slug, _ = shown_question
        theirs = "Public libraries are the last free public space we have left."
        mine = "Public libraries are the last free public space we really have left."
        target = answer_as(slug, theirs, token="device-first")

        page = open_demo(browser)
        page.wait_for_selector("#rhiz-demo-answer", timeout=45000)
        page.fill("#rhiz-demo-answer", mine)
        page.click("#rhiz-demo-submit")
        page.wait_for_selector("#rhiz-demo-keep", timeout=30000)

        with rx.session() as session:
            swaps_before = len(
                session.exec(
                    select(RoomSwap).where(RoomSwap.room_id == _room(session, slug).id)
                    .where(RoomSwap.to_reckoning_id == target)
                ).all()
            )

        page.click("button:has-text('Support this')")
        deadline = time.time() + 20
        swaps_after = swaps_before
        while time.time() < deadline and swaps_after == swaps_before:
            with rx.session() as session:
                swaps_after = len(
                    session.exec(
                        select(RoomSwap).where(
                            RoomSwap.room_id == _room(session, slug).id
                        )
                        .where(RoomSwap.to_reckoning_id == target)
                    ).all()
                )
            time.sleep(0.6)

        assert swaps_after == swaps_before + 1, (
            "the vote did not land on the wording it was offered"
        )
        assert "backed someone else" in body(page)
        assert mine not in body(page), "the withdrawn wording is still on screen"
        page.context.close()

    def test_it_reports_no_errors_of_its_own(self, browser, shown_question):
        """The hydration mismatch on every page is a known app-shell defect
        (rx.html meta tags render a <div> inside <head>); nothing else may
        appear."""
        page = open_demo(browser)
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.wait_for_selector("#rhiz-demo-answer", timeout=45000)
        page.reload(wait_until="networkidle")
        page.wait_for_selector("#rhiz-demo-answer", timeout=45000)
        assert [e for e in errors if "Hydration" not in e] == []
        page.context.close()


@needs_db
@needs_browser
class TestTheAdminPanel:
    """The dropdown the client asked for, driven the way they would drive it."""

    ORGANISER = "demo_organiser"
    PASSWORD = "Test_pass123"

    @pytest.fixture()
    def signed_in(self, browser, organiser):
        page = browser.new_context().new_page()
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(2000)
        page.fill("input[placeholder='Username']", self.ORGANISER)
        page.fill("input[type=password]", self.PASSWORD)
        page.click("button[type=submit]")
        # Wait for the login to actually take before navigating on: leaving too
        # early races the session cookie, and /live then renders as a stranger.
        page.wait_for_url(
            lambda url: not url.startswith(f"{BASE}/login"), timeout=25000
        )
        # Let the login round trip settle before navigating on; navigating
        # immediately races the session cookie and /live can render as a
        # stranger. (Waiting on body text here is unreliable: the redirect
        # target can be briefly empty while React hydrates.)
        page.wait_for_timeout(1500)
        page.goto(f"{BASE}/live", wait_until="networkidle", timeout=90000)
        page.wait_for_selector("text=Live Q&A", timeout=45000)
        yield page
        page.context.close()

    @pytest.fixture()
    def viewer(self):
        """An ordinary enabled account — the one `/live` is open to."""
        from rhiz.utils.security import hash_password

        with rx.session() as session:
            user = session.exec(
                select(User).where(User.username == "demo_viewer")
            ).first()
            if user is None:
                user = User(
                    username="demo_viewer",
                    email="demo_viewer@test.local",
                    password=hash_password("Test_pass123"),
                    enabled=True,
                    role=0,
                    can_create_groups=True,
                    created_at=datetime.datetime.now(datetime.timezone.utc),
                )
                session.add(user)
                session.commit()
                session.refresh(user)
        return "demo_viewer", "Test_pass123"

    def test_a_non_admin_is_not_offered_the_global_control(
        self, browser, viewer, demo_question
    ):
        """The pointer is site-wide. Hiding the control is not the security
        boundary (the handler checks too), but a non-admin must not be shown a
        setting that changes what a printed address displays for everybody."""
        username, password = viewer
        page = browser.new_context().new_page()
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(2000)
        page.fill("input[placeholder='Username']", username)
        page.fill("input[type=password]", password)
        page.click("button[type=submit]")
        page.wait_for_url(
            lambda url: not url.startswith(f"{BASE}/login"), timeout=25000
        )
        page.goto(f"{BASE}/live", wait_until="networkidle", timeout=90000)
        page.wait_for_selector("text=Live Q&A", timeout=45000)
        text = body(page)
        assert "Demo page (/demo)" not in text
        assert "rhiz-demo-question-select" not in page.content()
        page.context.close()

    def test_the_dashboard_offers_a_demo_question_picker(self, signed_in, demo_question):
        assert "Demo page (/demo)" in body(signed_in)

    def test_a_question_can_be_created_without_a_timer(self, organiser, signed_in):
        question = f"Asked from the dashboard [{uuid.uuid4().hex[:6]}]"
        signed_in.click("button:has-text('+ New room')")
        signed_in.wait_for_selector("[data-state=open] textarea", timeout=30000)
        signed_in.fill("[data-state=open] textarea", question)
        signed_in.click("[data-state=open] [role=combobox]")
        signed_in.wait_for_timeout(700)
        signed_in.click("[role=option]:has-text('no timer')")
        signed_in.click("[data-state=open] button:has-text('Create room')")

        deadline = time.time() + 25
        slug = None
        while time.time() < deadline and slug is None:
            with rx.session() as session:
                row = session.exec(
                    select(Group).where(Group.founding_question == question)
                ).first()
                if row is not None and row.close_at is None:
                    slug = row.slug
            time.sleep(0.6)
        try:
            assert slug is not None, "no permanent question was created"
            assert "No timer" in body(signed_in), (
                "the room page still advertises a countdown for a question that "
                "has none"
            )
        finally:
            if slug:
                with rx.session() as session:
                    _purge(session, _room(session, slug))

    def test_choosing_a_question_moves_the_public_page(self, demo_question, signed_in):
        slug, question = demo_question
        # The panel's option list is built when the page loads, so it has to be
        # loaded again now that the question under test exists.
        signed_in.goto(f"{BASE}/live", wait_until="networkidle", timeout=90000)
        signed_in.wait_for_selector("#rhiz-demo-question-select", timeout=30000)
        with rx.session() as session:
            # Point /demo at something else first, so that moving it is a real
            # change rather than a no-op the test could not distinguish.
            other = session.exec(
                select(Group).where(
                    Group.close_at == None,  # noqa: E711
                    Group.is_room == True,  # noqa: E712
                    Group.slug != slug,
                )
            ).first()
            if other is None:
                pytest.skip("needs a second permanent question to switch between")
            original = demo.read_active_slug(session)
            demo.write_active_slug(session, other.slug)

        try:
            signed_in.click("#rhiz-demo-question-select")
            signed_in.wait_for_timeout(900)
            signed_in.click(f"[role=option]:has-text('{question[:32]}')")
            # wait for the pick to register before applying it, rather than
            # hoping the state round trip beat the next click
            signed_in.wait_for_selector(
                f"#rhiz-demo-question-select:has-text('{question[:24]}')", timeout=15000
            )
            signed_in.click("#rhiz-demo-apply")

            deadline = time.time() + 20
            moved = False
            while time.time() < deadline and not moved:
                with rx.session() as session:
                    moved = demo.read_active_slug(session) == slug
                time.sleep(0.6)
            assert moved, "the dropdown did not move what /demo asks"
            assert "asks this question now" in body(signed_in), (
                "the panel gave no confirmation, and an organiser cannot tell "
                "whether the printed address changed"
            )
        finally:
            with rx.session() as session:
                if original:
                    demo.write_active_slug(session, original)
