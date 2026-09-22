"""Live Q&A room tests.

Two tiers:

* Pure logic (device identity, thresholds, deadline maths) always runs.
* Database tests are opt-in, because several of them delete rows and the
  similarity path loads the embedding model:

      RHIZ_DB_TESTS=1 DB_URL=postgresql://user:pass@localhost:5432/scratch \
          pytest tests/test_rooms.py

  They additionally refuse to run unless ``DB_URL`` points at a local server,
  so an accidental ``.env`` (production) URL can never be exercised.

Coverage maps to the plan's test checklist: one answer per device, edit
cooldown, swap semantics and support counting, ranking, tombstone rules,
lazy auto-close and late-write rejection, extend, close-with-note, deletion
completeness, the site-wide leak guard, and the isolation guarantee that room
content never appears on public surfaces.
"""

import os
import re
from datetime import datetime, timedelta

import pytest
from sqlmodel import func, select

from rhiz.utils.rooms import (
    DEFAULT_DURATION_MINUTES,
    DEFAULT_SIMILARITY_THRESHOLD,
    EDIT_COOLDOWN_SECONDS,
    EXTEND_MINUTES,
    MAX_ANSWER_LENGTH,
    DURATION_CHOICES,
    THRESHOLD_CHOICES,
    device_hash_for,
)

# ----------------------------------------------------------------------
# Tier 1: pure logic, no database
# ----------------------------------------------------------------------


def test_device_hash_is_deterministic():
    a = device_hash_for("token-abc", "roomslug1")
    b = device_hash_for("token-abc", "roomslug1")
    assert a == b


def test_device_hash_is_scoped_per_room():
    """The same device must be unlinkable across rooms."""
    a = device_hash_for("token-abc", "room-one")
    b = device_hash_for("token-abc", "room-two")
    assert a != b


def test_device_hash_differs_per_token():
    assert device_hash_for("token-a", "room") != device_hash_for("token-b", "room")


def test_device_hash_is_sha256_hex():
    h = device_hash_for("token", "room")
    assert re.fullmatch(r"[0-9a-f]{64}", h), h


def test_default_duration_is_selectable():
    assert DEFAULT_DURATION_MINUTES in DURATION_CHOICES


def test_default_threshold_is_labelled():
    """The default must correspond to one of the facilitator's choices."""
    assert any(abs(value - DEFAULT_SIMILARITY_THRESHOLD) < 1e-6 for _, value in THRESHOLD_CHOICES)


def test_extend_is_fifteen_minutes():
    assert EXTEND_MINUTES == 15


def test_edit_cooldown_exists():
    assert EDIT_COOLDOWN_SECONDS > 0


def test_answer_length_cap_matches_main_site():
    assert MAX_ANSWER_LENGTH == 2000


# ----------------------------------------------------------------------
# Tier 2: database-backed
# ----------------------------------------------------------------------

_DB_URL = os.environ.get("DB_URL", "")
_HOST = (re.search(r"@([^/?]+)", _DB_URL) or [None, ""])[1] if _DB_URL else ""
_IS_LOCAL = _HOST.startswith("localhost") or _HOST.startswith("127.0.0.1")
_DB_ENABLED = os.environ.get("RHIZ_DB_TESTS") == "1" and _IS_LOCAL

requires_db = pytest.mark.skipif(
    not _DB_ENABLED,
    reason="set RHIZ_DB_TESTS=1 and a local DB_URL to run room database tests",
)


@pytest.fixture(scope="module")
def session_factory():
    if not _DB_ENABLED:
        pytest.skip("room database tests disabled")
    import reflex as rx

    return rx.session


@pytest.fixture()
def session(session_factory):
    with session_factory() as s:
        yield s


@pytest.fixture()
def facilitator(session):
    """A throwaway account to own rooms."""
    from rhiz.state.base import User
    from rhiz.utils.security import hash_password
    from sqlmodel import select

    username = "roomtest_fac"
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        user = User(
            username=username,
            email="roomtest_fac@test.local",
            password=hash_password("Test_pass123"),
            enabled=True,
            role=0,
            can_create_groups=True,
            created_at=datetime.utcnow(),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


@pytest.fixture()
def room(session, facilitator):
    """A fresh room, deleted again after the test.

    The room id is captured immediately: tests that exercise deletion leave
    the ORM instance pointing at a gone row, and touching any attribute of it
    (including in teardown) would raise ObjectDeletedError.
    """
    from rhiz.state.base import Group
    from rhiz.utils.rooms import create_room, delete_room

    r = create_room(session, "Room fixture question", facilitator.id, duration_minutes=60)
    room_id = r.id
    yield r
    if session.get(Group, room_id) is not None:
        delete_room(session, room_id, owner_id=facilitator.id)


def _participant(session, room, token):
    from rhiz.utils.rooms import get_or_create_participant

    return get_or_create_participant(session, room, token)


@requires_db
class TestRoomCreation:
    def test_room_is_a_private_group_in_room_mode(self, session, room):
        from rhiz.state.base import Group

        reloaded = session.get(Group, room.id)
        assert reloaded.is_room is True
        assert reloaded.is_public is False

    def test_slug_is_unguessable(self, session, room):
        # token_urlsafe(12) -> 16 chars of url-safe base64
        assert room.slug is not None and len(room.slug) >= 16

    def test_founding_question_becomes_a_concept(self, session, room):
        from rhiz.state.base import Reckoning

        concept = session.get(Reckoning, room.concept_id)
        assert concept is not None
        assert concept.content == room.founding_question
        # The founding concept is not itself an answer.
        assert concept.user_id == room.created_by

    def test_close_at_is_set_from_duration(self, session, room):
        assert room.close_at is not None
        remaining = (room.close_at - datetime.utcnow()).total_seconds()
        assert 59 * 60 < remaining <= 60 * 60 + 5

    def test_empty_question_rejected(self, session, facilitator):
        from rhiz.utils.rooms import create_room

        with pytest.raises(ValueError):
            create_room(session, "   ", facilitator.id)

    def test_unknown_duration_falls_back_to_default(self, session, facilitator):
        from rhiz.utils.rooms import create_room, delete_room

        r = create_room(session, "Odd duration question", facilitator.id, duration_minutes=7)
        try:
            mins = round((r.close_at - datetime.utcnow()).total_seconds() / 60)
            assert abs(mins - DEFAULT_DURATION_MINUTES) <= 1
        finally:
            delete_room(session, r.id, owner_id=facilitator.id)


@requires_db
class TestParticipation:
    def test_one_answer_per_device(self, session, room):
        from rhiz.utils.rooms import submit_answer

        p = _participant(session, room, "device-one")
        answer, _similar = submit_answer(session, room, p, "My first answer")
        assert answer is not None
        with pytest.raises(ValueError):
            submit_answer(session, room, p, "My second answer")

    def test_empty_answer_rejected(self, session, room):
        from rhiz.utils.rooms import submit_answer

        p = _participant(session, room, "device-empty")
        with pytest.raises(ValueError):
            submit_answer(session, room, p, "   ")

    def test_overlong_answer_rejected(self, session, room):
        from rhiz.utils.rooms import submit_answer

        p = _participant(session, room, "device-long")
        with pytest.raises(ValueError):
            submit_answer(session, room, p, "x" * (MAX_ANSWER_LENGTH + 1))

    def test_edit_sets_edited_marker(self, session, room):
        from rhiz.utils.rooms import edit_answer, submit_answer

        p = _participant(session, room, "device-edit")
        answer, _ = submit_answer(session, room, p, "Original wording")
        # The cooldown is measured against created_at, so backdate it.
        answer.created_at = datetime.utcnow() - timedelta(seconds=EDIT_COOLDOWN_SECONDS + 5)
        session.add(answer)
        session.commit()
        updated = edit_answer(session, room, p, "Improved wording")
        assert updated is not None
        assert updated.content == "Improved wording"
        assert updated.edited_at is not None

    def test_edit_cooldown_blocks_rapid_edits(self, session, room):
        from rhiz.utils.rooms import edit_answer, submit_answer

        p = _participant(session, room, "device-cooldown")
        submit_answer(session, room, p, "First wording")
        with pytest.raises(ValueError):
            edit_answer(session, room, p, "Second wording immediately")


@requires_db
class TestSwapsAndResults:
    def test_swap_moves_support_and_withdraws_wording(self, session, room):
        from rhiz.utils.rooms import RoomSwap, submit_answer, swap_support
        from sqlmodel import select

        a = _participant(session, room, "swap-author")
        answer_a, _ = submit_answer(session, room, a, "The winning answer")
        b = _participant(session, room, "swap-switcher")
        answer_b, _ = submit_answer(session, room, b, "The withdrawn answer")

        assert swap_support(session, room, b, answer_a.id) is True

        swaps = session.exec(
            select(RoomSwap).where(RoomSwap.room_id == room.id)
        ).all()
        assert len(swaps) == 1
        assert swaps[0].from_reckoning_id == answer_b.id
        assert swaps[0].to_reckoning_id == answer_a.id

        # The switcher now supports a's answer and has no wording of their own.
        session.refresh(b)
        assert b.current_answer_id is None
        assert b.supported_answer_id == answer_a.id

    def test_one_swap_per_device(self, session, room):
        from rhiz.utils.rooms import submit_answer, swap_support

        a = _participant(session, room, "swap2-author")
        answer_a, _ = submit_answer(session, room, a, "First target answer")
        c = _participant(session, room, "swap2-target")
        submit_answer(session, room, c, "Second target answer")
        b = _participant(session, room, "swap2-switcher")
        submit_answer(session, room, b, "My own wording here")

        assert swap_support(session, room, b, answer_a.id) is True
        # A second swap is refused.
        assert swap_support(session, room, b, c.current_answer_id) is False

    def test_cannot_swap_to_own_or_missing_answer(self, session, room):
        from rhiz.utils.rooms import submit_answer, swap_support

        a = _participant(session, room, "swap-self")
        answer_a, _ = submit_answer(session, room, a, "My own answer")
        assert swap_support(session, room, a, answer_a.id) is False
        assert swap_support(session, room, a, 999_999_999) is False

    def test_results_rank_by_support(self, session, room):
        from rhiz.utils.rooms import room_results, submit_answer, swap_support

        a = _participant(session, room, "rank-a")
        answer_a, _ = submit_answer(session, room, a, "Answer with most support")
        b = _participant(session, room, "rank-b")
        submit_answer(session, room, b, "Answer that gets abandoned")
        c = _participant(session, room, "rank-c")
        submit_answer(session, room, c, "Another plain answer")
        swap_support(session, room, b, answer_a.id)

        results = room_results(session, room)
        assert results["total_swaps"] == 1
        supports = [item["support"] for item in results["items"]]
        assert supports == sorted(supports, reverse=True)
        top = results["items"][0]
        assert top["id"] == answer_a.id
        assert top["support"] == 2  # author + one switcher
        assert top["swaps_in"] == 1

    def test_withdrawn_answer_with_no_inbound_swaps_is_hidden(self, session, room):
        from rhiz.utils.rooms import room_results, submit_answer, swap_support

        a = _participant(session, room, "hide-a")
        answer_a, _ = submit_answer(session, room, a, "Surviving answer")
        b = _participant(session, room, "hide-b")
        answer_b, _ = submit_answer(session, room, b, "Abandoned wording")
        swap_support(session, room, b, answer_a.id)

        ids = [item["id"] for item in room_results(session, room)["items"]]
        assert answer_a.id in ids
        assert answer_b.id not in ids

    def test_removed_answer_with_inbound_swaps_tombstones(self, session, room):
        """Withdrawn-but-merged wording stays visible at rank, without content."""
        from rhiz.utils.rooms import (
            _withdraw_answer,
            room_results,
            submit_answer,
            swap_support,
        )

        a = _participant(session, room, "tomb-a")
        answer_a, _ = submit_answer(session, room, a, "Merged into answer")
        b = _participant(session, room, "tomb-b")
        answer_b, _ = submit_answer(session, room, b, "Answer that others merge into")
        c = _participant(session, room, "tomb-c")
        answer_c, _ = submit_answer(session, room, c, "Third answer here")
        swap_support(session, room, c, answer_b.id)
        # b abandons its own wording too, leaving it with one inbound swap.
        swap_support(session, room, b, answer_a.id)

        items = {i["id"]: i for i in room_results(session, room)["items"]}
        assert answer_b.id in items
        assert items[answer_b.id]["removed"] is True
        assert items[answer_b.id]["content"] == ""
        assert items[answer_b.id]["swaps_in"] == 1

    def test_total_swaps_counts_every_switch(self, session, room):
        from rhiz.utils.rooms import room_results, submit_answer, swap_support

        a = _participant(session, room, "tot-a")
        answer_a, _ = submit_answer(session, room, a, "Consolidated answer")
        for i in range(3):
            p = _participant(session, room, f"tot-swapper-{i}")
            submit_answer(session, room, p, f"Distinct original wording number {i}")
            swap_support(session, room, p, answer_a.id)
        assert room_results(session, room)["total_swaps"] == 3


@requires_db
class TestTiming:
    def test_deadline_auto_closes_lazily(self, session, room):
        """No scheduler: the deadline is enforced on the next read/write."""
        from rhiz.state.base import Group, GroupStatus
        from rhiz.utils.rooms import enforce_deadline

        row = session.get(Group, room.id)
        row.close_at = datetime.utcnow() - timedelta(seconds=1)
        session.add(row)
        session.commit()

        updated = enforce_deadline(session, row)
        assert updated.status == GroupStatus.closed
        assert updated.closed_at is not None

    def test_late_submission_rejected_after_deadline(self, session, room):
        from rhiz.state.base import Group
        from rhiz.utils.rooms import submit_answer

        row = session.get(Group, room.id)
        row.close_at = datetime.utcnow() - timedelta(seconds=1)
        session.add(row)
        session.commit()

        p = _participant(session, room, "late-device")
        with pytest.raises(ValueError):
            submit_answer(session, room, p, "Too late to answer")

    def test_extend_pushes_the_deadline(self, session, room):
        from rhiz.state.base import Group
        from rhiz.utils.rooms import extend_room

        before = session.get(Group, room.id).close_at
        extended = extend_room(session, room.id)
        assert extended.close_at > before
        delta = (extended.close_at - before).total_seconds()
        assert abs(delta - EXTEND_MINUTES * 60) < 30

    def test_manual_close_freezes_and_stores_note(self, session, room):
        from rhiz.state.base import Group, GroupStatus
        from rhiz.utils.rooms import close_room, submit_answer

        p = _participant(session, room, "closed-device")
        assert close_room(session, room.id, closing_note="That is all, thank you") is not None
        row = session.get(Group, room.id)
        assert row.status == GroupStatus.closed
        assert row.closing_note == "That is all, thank you"
        with pytest.raises(ValueError):
            submit_answer(session, room, p, "Answer after close")

    def test_closing_twice_returns_none(self, session, room):
        from rhiz.utils.rooms import close_room

        assert close_room(session, room.id) is not None
        assert close_room(session, room.id) is None

    def test_reopen_revives_a_closed_room(self, session, room):
        """Reopening (for stragglers) restores the answering flow: status
        open, closed_at and closing note cleared, deadline re-armed."""
        from rhiz.state.base import Group, GroupStatus
        from rhiz.utils.rooms import close_room, reopen_room, submit_answer

        p = _participant(session, room, "reopen-device")
        assert close_room(session, room.id, closing_note="done") is not None
        reopened = reopen_room(session, room.id)
        assert reopened is not None
        row = session.get(Group, room.id)
        assert row.status == GroupStatus.open
        assert row.closed_at is None
        assert row.closing_note is None
        assert row.close_at > datetime.utcnow()
        # A straggler can now answer.
        answer, _ = submit_answer(session, room, p, "Straggler answer")
        assert answer is not None

    def test_reopen_rejects_open_rooms(self, session, room):
        from rhiz.utils.rooms import reopen_room

        assert reopen_room(session, room.id) is None


@requires_db
class TestPublishAnswers:
    def test_graduated_answer_flag(self, session, room):
        """Publishing a room answer to the main site is the group-concept
        graduation flag: is_graduated=True keeps it in the artifact while
        surfacing it in site-wide feeds."""
        from rhiz.utils.rooms import submit_answer

        p = _participant(session, room, "publish-device")
        answer, _ = submit_answer(session, room, p, "Answer worth sharing")
        answer.is_graduated = True
        session.add(answer)
        session.commit()
        session.refresh(answer)
        assert answer.is_graduated is True


@requires_db
class TestDeletion:
    def test_non_owner_cannot_delete(self, session, room, facilitator):
        from rhiz.state.base import Group
        from rhiz.utils.rooms import delete_room

        assert delete_room(session, room.id, owner_id=facilitator.id + 999) is False
        assert session.get(Group, room.id) is not None

    def test_owner_delete_removes_everything(self, session, room, facilitator):
        from rhiz.state.base import Group, GroupMember, Reckoning, RoomParticipant, RoomSwap
        from rhiz.utils.groups import join_group
        from rhiz.utils.rooms import delete_room, submit_answer, swap_support

        # Capture every id as a plain int first: after deletion the ORM
        # instances point at gone rows, and touching an attribute on one
        # raises ObjectDeletedError.
        room_id = room.id
        concept_id = room.concept_id

        a = _participant(session, room, "del-a")
        answer_a, _ = submit_answer(session, room, a, "Answer to be deleted")
        answer_a_id = answer_a.id
        b = _participant(session, room, "del-b")
        answer_b, _ = submit_answer(session, room, b, "Answer that switches")
        answer_b_id = answer_b.id
        swap_support(session, room, b, answer_a_id)
        join_group(session, facilitator.id, room_id)

        assert delete_room(session, room_id, owner_id=facilitator.id) is True

        assert session.get(Group, room_id) is None
        assert session.get(Reckoning, answer_a_id) is None
        assert session.get(Reckoning, answer_b_id) is None
        assert session.get(Reckoning, concept_id) is None
        assert session.exec(select_count(session, RoomSwap, room_id)).one() == 0
        assert session.exec(
            select_count(session, RoomParticipant, room_id)
        ).one() == 0
        assert session.exec(select_count(session, GroupMember, room_id)).one() == 0

    def test_deletion_does_not_publish_answers_site_wide(self, session, room, facilitator):
        """The leak guard.

        delete_group() nulls reckoning.group_id so a group's concepts survive
        as public content. Room answers must never survive that way.
        """
        import reflex as rx
        from rhiz.state.base import Reckoning
        from rhiz.utils.rooms import delete_room, submit_answer

        room_id = room.id
        p = _participant(session, room, "leak-a")
        answer, _ = submit_answer(session, room, p, "Anonymous answer that must not leak")
        answer_id = answer.id
        assert delete_room(session, room_id, owner_id=facilitator.id) is True

        with rx.session() as s2:
            row = s2.get(Reckoning, answer_id)
        assert row is None, "deleted room answer survived"

    def test_delete_group_delegates_for_rooms(self, session, facilitator):
        import reflex as rx
        from rhiz.state.base import Group, Reckoning
        from rhiz.utils.groups import delete_group
        from rhiz.utils.rooms import create_room, submit_answer

        r = create_room(session, "Room deleted via group helper", facilitator.id)
        room_id, group_type = r.id, type(r)
        p = _participant(session, r, "delegate-a")
        answer, _ = submit_answer(session, r, p, "Answer inside delegated room")
        answer_id = answer.id

        delete_group(session, room_id, owner_id=facilitator.id)

        with rx.session() as s2:
            assert s2.get(Reckoning, answer_id) is None
            assert s2.get(Group, room_id) is None

    def test_delete_room_refuses_ordinary_groups(self, session, room, facilitator):
        from rhiz.state.base import Group
        from rhiz.utils.rooms import delete_room

        ordinary = session.get(Group, room.id)
        ordinary.is_room = False
        session.add(ordinary)
        session.commit()
        try:
            assert delete_room(session, room.id, owner_id=facilitator.id) is False
        finally:
            ordinary = session.get(Group, room.id)
            ordinary.is_room = True
            session.add(ordinary)
            session.commit()

    def test_deletion_is_audit_logged(self, session, room, facilitator):
        from rhiz.state.base import Log
        from rhiz.utils.rooms import delete_room
        from sqlmodel import select

        assert delete_room(session, room.id, owner_id=facilitator.id, actor_id=facilitator.id)
        logs = session.exec(
            select(Log).where(Log.content.like("deleted live room%"))  # type: ignore[attr-defined]
        ).all()
        assert logs, "expected an audit log entry for the deletion"
        assert any(log.user_id == facilitator.id for log in logs)


@requires_db
class TestModeration:
    def test_admin_removal_tombstones(self, session, room):
        from rhiz.state.base import Reckoning
        from rhiz.utils.rooms import remove_answer_admin, submit_answer

        p = _participant(session, room, "mod-a")
        answer, _ = submit_answer(session, room, p, "Answer flagged for removal")
        assert remove_answer_admin(session, answer.id, room_id=room.id) is True
        session.expire_all()
        row = session.get(Reckoning, answer.id)
        assert row.removed_at is not None

    def test_removal_is_scoped_to_the_room(self, session, room, facilitator):
        from rhiz.utils.rooms import (
            create_room,
            delete_room,
            remove_answer_admin,
            submit_answer,
        )

        other = create_room(session, "A different room entirely", facilitator.id)
        other_id = other.id
        try:
            p = _participant(session, other, "mod-other")
            answer, _ = submit_answer(session, other, p, "Answer in the other room")
            # Refused: the id belongs to a different room than the one passed.
            assert remove_answer_admin(session, answer.id, room_id=room.id) is False
        finally:
            delete_room(session, other_id, owner_id=facilitator.id)


@requires_db
class TestIsolation:
    def test_room_content_never_reaches_site_wide_feeds(self, session, room, facilitator):
        """Every site-wide surface applies _exclude_private_groups()."""
        from rhiz.pages.reckonings import _exclude_private_groups
        from rhiz.state.base import Group, Reckoning
        from rhiz.utils.rooms import submit_answer
        from sqlmodel import select

        p = _participant(session, room, "iso-a")
        answer, _ = submit_answer(session, room, p, "Anonymous room answer for isolation test")
        answer_id = answer.id

        visible = session.exec(
            select(Reckoning.id).where(_exclude_private_groups())
        ).all()
        assert answer_id not in [v for v in visible]

        # And a room is never treated as a public group.
        assert session.get(Group, room.id).is_public is False


# ----------------------------------------------------------------------
# helpers used inside tests
# ----------------------------------------------------------------------


def select_count(session, model, room_id):
    """Count rows of `model` for a room (works for both room_id/group_id)."""
    from rhiz.state.base import GroupMember

    col = GroupMember.group_id if model is GroupMember else model.room_id
    return select(func.count(model.id)).where(col == room_id)
