"""The live-room outbox: writes a bad connection could not deliver.

The behaviour that matters here is not "can we retry" — anything can retry. It
is that retrying a live room is *safe*, because a phone on bad wifi cannot tell
the difference between a write that failed and a write whose response was lost:

    the tap is held on the device, sent, and if the response never arrives the
    same intent is sent again later.

So every test below is really about one of two things: that a replay cannot
double-post (desired-state application), and that the browser is treated as a
stranger (its localStorage is untrusted input, and the two halves of this
feature are written in different languages with no compiler between them).
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

import pytest

from rhiz.utils import outbox

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_DB_URL = os.environ.get("DB_URL", "")
_HOST = (re.search(r"@([^/?]+)", _DB_URL) or [None, ""])[1] if _DB_URL else ""
_IS_LOCAL = _HOST.startswith("localhost") or _HOST.startswith("127.0.0.1")
_DB_ENABLED = os.environ.get("RHIZ_DB_TESTS") == "1" and _IS_LOCAL

requires_db = pytest.mark.skipif(
    not _DB_ENABLED, reason="set RHIZ_DB_TESTS=1 and a local DB_URL"
)


def _now_ms(minutes_ago: float = 0) -> int:
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return int(moment.timestamp() * 1000)


def _payload(**kinds) -> str:
    return json.dumps(kinds)


# ----------------------------------------------------------------------
# Tier 1: what the browser is allowed to hand us
# ----------------------------------------------------------------------


class TestDecoding:
    def test_a_plain_answer_intent_survives(self):
        decoded = outbox.decode_intents(
            _payload(answer={"text": "  less meetings  ", "at": _now_ms()})
        )
        assert decoded == {"answer": {"text": "less meetings"}}

    def test_support_keeps_its_target(self):
        decoded = outbox.decode_intents(
            _payload(support={"reckoning_id": 42, "at": _now_ms()})
        )
        assert decoded["support"]["reckoning_id"] == 42

    def test_intents_come_back_in_the_order_they_must_be_applied(self):
        """Support withdraws your own answer, so it has to go last; an edit is
        meaningless before the answer exists."""
        raw = _payload(
            support={"reckoning_id": 1, "at": _now_ms()},
            edit={"text": "b", "at": _now_ms()},
            answer={"text": "a", "at": _now_ms()},
        )
        assert list(outbox.decode_intents(raw)) == ["answer", "edit", "support"]

    def test_draft_is_not_an_intent(self):
        """Held typing is never an intent: nobody has chosen to send it."""
        assert outbox.decode_intents(_payload(draft="half a thought")) == {}

    def test_unknown_keys_are_ignored(self):
        assert outbox.decode_intents(_payload(nonsense={"x": 1})) == {}


class TestRefusingBadInput:
    """The payload is localStorage: it can be stale, truncated, or typed by
    hand into dev tools. Nothing here may raise, and nothing here may be
    applied without being understood."""

    @pytest.mark.parametrize(
        "payload",
        [
            None,
            42,
            "",
            "not json",
            "[]",
            '"a string"',
            json.dumps(["answer"]),
        ],
    )
    def test_rubbish_decodes_to_nothing(self, payload):
        assert outbox.decode_intents(payload) == {}

    def test_oversized_payload_is_refused_whole(self):
        """A browser with a hand-edited 10 MB answer must not become a server
        problem — or an outage for the other 40 devices in the room."""
        huge = _payload(answer={"text": "x" * (outbox.MAX_PAYLOAD_CHARS + 10), "at": _now_ms()})
        assert outbox.decode_intents(huge) == {}

    def test_text_over_the_answer_limit_is_dropped(self):
        raw = _payload(answer={"text": "x" * 5000, "at": _now_ms()})
        assert outbox.decode_intents(raw) == {}

    def test_blank_text_is_dropped(self):
        assert outbox.decode_intents(_payload(answer={"text": "   ", "at": _now_ms()})) == {}

    @pytest.mark.parametrize("target", [0, -3, "7", 1.5, True, None])
    def test_support_target_must_be_a_real_id(self, target):
        raw = _payload(support={"reckoning_id": target, "at": _now_ms()})
        assert outbox.decode_intents(raw) == {}

    def test_text_must_be_text(self):
        assert outbox.decode_intents(_payload(answer={"text": 99, "at": _now_ms()})) == {}

    def test_entry_must_be_an_object(self):
        assert outbox.decode_intents(_payload(answer="just a string")) == {}

    @pytest.mark.parametrize("stamp", [None, "now", True, {}, 10**18])
    def test_undateable_intents_are_refused(self, stamp):
        """No timestamp means no way to bound how stale it is, so it cannot be
        applied to a room that may have closed since."""
        raw = _payload(answer={"text": "hi", "at": stamp})
        assert outbox.decode_intents(raw) == {}

    def test_an_intent_older_than_the_window_is_gone(self):
        """The room it belonged to closed an hour ago; landing it now would be
        worse than losing it."""
        raw = _payload(
            answer={"text": "stale", "at": _now_ms(outbox.MAX_INTENT_AGE_MINUTES + 5)}
        )
        assert outbox.decode_intents(raw) == {}

    def test_the_window_is_a_sliding_one(self):
        raw = _payload(answer={"text": "recent", "at": _now_ms(3)})
        assert "answer" in outbox.decode_intents(raw)

    def test_a_clock_a_few_minutes_fast_is_tolerated(self):
        """Phone clocks disagree with servers; refusing on a two-minute skew
        would drop perfectly good answers."""
        raw = _payload(
            answer={
                "text": "nearly now",
                "at": _now_ms(-outbox.MAX_CLOCK_SKEW_MINUTES // 2),
            }
        )
        assert "answer" in outbox.decode_intents(raw)

    def test_a_clock_hours_fast_is_not(self):
        raw = _payload(
            answer={"text": "from the future", "at": _now_ms(-600)}
        )
        assert outbox.decode_intents(raw) == {}


class TestClearing:
    def test_clear_names_only_real_kinds(self):
        js = outbox.clear_intents_js(["answer", "nonsense", "'; drop table"])
        assert "answer" in js
        assert "nonsense" not in js
        assert "drop table" not in js

    def test_clear_defaults_to_everything(self):
        js = outbox.clear_intents_js()
        for kind in outbox.KINDS:
            assert kind in js

    def test_draft_can_be_cleared_too(self):
        assert "draft" in outbox.clear_intents_js(["answer", "draft"])

    def test_pending_count_is_the_number_of_intents(self):
        assert outbox.pending_count({"answer": {}, "support": {}}) == 2
        assert outbox.pending_count({}) == 0


# ----------------------------------------------------------------------
# Tier 1b: the two halves must actually speak to each other
#
# assets/outbox.js (browser) and rhiz/pages/room.py (server) are written in
# different languages, so nothing but these tests notices when one side renames
# something. A drift here fails silently in the worst way: on the day of the
# conference, with the queue quietly never draining.
# ----------------------------------------------------------------------


def _read(*parts) -> str:
    with open(os.path.join(_ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def asset_js() -> str:
    return _read("assets", "outbox.js")


@pytest.fixture(scope="module")
def page_py() -> str:
    return _read("rhiz", "pages", "room.py")


class TestBothHalvesAgree:
    def test_every_helper_the_page_calls_exists_in_the_asset(self, asset_js, page_py):
        called = set(re.findall(r"window\.(rhiz[A-Za-z]+)", page_py))
        assert called, "the page is expected to call into the outbox asset"
        for name in called:
            # calls are written `window.rhizX&&window.rhizX()` so that a tap
            # before the asset has loaded is a no-op rather than a crash — which
            # means the asset really has to define the name.
            assert f"window.{name}" in asset_js, f"assets/outbox.js never defines {name}"

    def test_taps_are_recorded_from_ids_the_page_renders(self, asset_js, page_py):
        """The queue-on-tap half must never be a Reflex event.

        A Reflex event — `rx.call_script` included — is dispatched over the
        websocket, so queueing that way only works while the socket does, which
        is the opposite of the case this feature exists for. The asset records
        taps by watching ids; this checks both sides name the same buttons.
        """
        assert "call_script(queue" not in page_py, (
            "queueing a tap through rx.call_script cannot run when the socket "
            "is down, which is the whole point"
        )
        for button_id in re.findall(r'(?:SUBMIT|SAVE)_ID = "([^"]+)"', asset_js):
            assert f'id="{button_id}"' in page_py, (
                f"assets/outbox.js queues taps on #{button_id}, which the page "
                "no longer renders"
            )
        support = re.search(r"SUPPORT_ID = /(.*?)/;", asset_js)
        assert support and "rhiz-support-" in page_py, (
            "the support button id and the asset's pattern have drifted apart"
        )

    def test_every_element_id_the_asset_reaches_for_is_rendered(self, asset_js, page_py):
        wanted = set(re.findall(r"_ID = \"([^\"]+)\"", asset_js))
        assert wanted, "expected the asset to reference element ids"
        for element_id in wanted:
            assert f'id="{element_id}"' in page_py, (
                f"assets/outbox.js looks for #{element_id}, but the room page "
                "does not render it"
            )

    def test_both_sides_use_the_same_storage_key(self, asset_js, outbox_py=_read("rhiz", "utils", "outbox.py")):
        assert outbox.OUTBOX_STORAGE_KEY in asset_js
        assert outbox.OUTBOX_STORAGE_KEY in outbox_py

    def test_the_page_clears_only_kinds_the_asset_understands(self, asset_js):
        for kind in outbox.KINDS:
            assert f'"{kind}"' in asset_js

    def test_the_queue_key_is_versioned(self):
        """Stale blobs from an older shape must be ignored, not parsed."""
        assert re.search(r"_v\d+$", outbox.OUTBOX_STORAGE_KEY), (
            "change the shape of the stored queue and bump the version suffix"
        )


# ----------------------------------------------------------------------
# Tier 2: applying intents to a real room
# ----------------------------------------------------------------------


@requires_db
class TestApplyingIntents:
    @pytest.fixture()
    def session(self):
        import reflex as rx

        with rx.session() as s:
            yield s

    @pytest.fixture()
    def room(self, session):
        from rhiz.state.base import User, set_setting
        from rhiz.utils.rooms import create_room
        from rhiz.utils.security import hash_password

        set_setting("auto_signup_enabled", "true")
        suffix = datetime.utcnow().strftime("%H%M%S%f")
        host = User(
            username=f"obthost{suffix[-9:]}",
            email=f"obthost_{suffix}@test.local",
            password=hash_password("Outbox_pass1"),
            enabled=True,
            role=0,
            can_create_groups=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        session.add(host)
        session.commit()
        session.refresh(host)
        room = create_room(session, "What should we stop doing?", host.id, 60)
        yield room
        from rhiz.utils.rooms import delete_room

        fresh = session.get(type(room), room.id)
        if fresh is not None:
            delete_room(session, fresh.id)
        row = session.get(User, host.id)
        if row is not None:
            session.delete(row)
        session.commit()

    def _device(self, session, room, tag):
        from rhiz.utils.rooms import get_or_create_participant

        return get_or_create_participant(session, room, f"device-{tag}")

    def _intents(self, session, room, participant, kinds):
        from rhiz.utils.outbox import apply_intents

        return apply_intents(session, room, participant, kinds)

    def _past_the_edit_cooldown(self, session, participant):
        """Age the answer instead of sleeping for it.

        The room throttles edits to one per ``EDIT_COOLDOWN_SECONDS``; a queued
        rewording normally arrives minutes after the tap, so waiting is not what
        is being modelled here.
        """
        from rhiz.state.base import Reckoning
        from rhiz.utils.rooms import EDIT_COOLDOWN_SECONDS

        answer = session.get(Reckoning, participant.current_answer_id)
        answer.created_at = datetime.utcnow() - timedelta(
            seconds=EDIT_COOLDOWN_SECONDS + 5
        )
        session.add(answer)
        session.commit()

    # -- the answer -----------------------------------------------------

    def test_a_queued_answer_lands(self, session, room):
        me = self._device(session, room, "a")
        outcomes = self._intents(
            session, room, me, {"answer": {"text": "Status meetings"}}
        )
        assert outcomes == {"answer": outbox.APPLIED}
        assert me.current_answer_id is not None

    def test_replaying_an_answer_does_not_post_it_twice(self, session, room):
        """The whole reason intents are desired states rather than commands.

        From a phone's point of view "the server created my answer and the reply
        was lost" and "the server never got it" are the same event, so the retry
        must not be able to produce two answers from one tap.
        """
        me = self._device(session, room, "replay")
        intent = {"answer": {"text": "Reply-all culture"}}
        assert self._intents(session, room, me, intent)["answer"] == outbox.APPLIED
        assert self._intents(session, room, me, intent)["answer"] == outbox.ALREADY

        from sqlmodel import select

        from rhiz.state.base import Reckoning

        rows = session.exec(
            select(Reckoning).where(
                Reckoning.group_id == room.id, Reckoning.content == "Reply-all culture"
            )
        ).all()
        assert len(rows) == 1

    def test_a_stale_revision_cannot_overwrite_a_newer_edit(self, session, room):
        """A queued edit that was superseded while the queue retried.

        The phone's clock cannot arbitrate this: an older intent whose revision
        is already behind the server's must be dropped, not applied over the
        newer wording.
        """
        me = self._device(session, room, "staleedit")
        self._intents(
            session, room, me, {"answer": {"text": "First wording", "version": 1}}
        )
        self._past_the_edit_cooldown(session, me)
        newer = {"edit": {"text": "Newer wording", "version": 2}}
        assert self._intents(session, room, me, newer)["edit"] == outbox.APPLIED
        outcomes = self._intents(
            session, room, me, {"edit": {"text": "Older wording", "version": 1}}
        )
        assert outcomes["edit"] == outbox.DROP
        from rhiz.utils.rooms import my_answer

        assert my_answer(session, me).content == "Newer wording"
        assert me.intent_version >= 2

    def test_replaying_a_versioned_edit_is_a_no_op(self, session, room):
        me = self._device(session, room, "versionreplay")
        self._intents(
            session, room, me, {"answer": {"text": "A", "version": 1}}
        )
        self._past_the_edit_cooldown(session, me)
        edit = {"edit": {"text": "B", "version": 2}}
        assert self._intents(session, room, me, edit)["edit"] == outbox.APPLIED
        assert self._intents(session, room, me, edit)["edit"] == outbox.ALREADY

    def test_a_stale_answer_never_overwrites_a_newer_one(self, session, room):
        """Two taps, sent in the wrong order: the later wording must win."""
        me = self._device(session, room, "stale")
        self._intents(session, room, me, {"answer": {"text": "Newer wording"}})
        outcomes = self._intents(
            session, room, me, {"answer": {"text": "Older wording"}}
        )
        assert outcomes["answer"] == outbox.DROP
        from rhiz.utils.rooms import my_answer

        assert my_answer(session, me).content == "Newer wording"

    # -- the edit -------------------------------------------------------

    def test_a_queued_edit_lands(self, session, room):
        me = self._device(session, room, "edit")
        self._intents(session, room, me, {"answer": {"text": "First wording"}})
        self._past_the_edit_cooldown(session, me)
        outcomes = self._intents(
            session, room, me, {"edit": {"text": "Second wording"}}
        )
        assert outcomes["edit"] == outbox.APPLIED
        from rhiz.utils.rooms import my_answer

        assert my_answer(session, me).content == "Second wording"

    def test_replaying_an_edit_is_a_no_op(self, session, room):
        me = self._device(session, room, "editreplay")
        self._intents(session, room, me, {"answer": {"text": "A"}})
        self._past_the_edit_cooldown(session, me)
        edit = {"edit": {"text": "B"}}
        assert self._intents(session, room, me, edit)["edit"] == outbox.APPLIED
        assert self._intents(session, room, me, edit)["edit"] == outbox.ALREADY

    def test_an_edit_without_an_answer_is_dropped(self, session, room):
        """The answer it belonged to never arrived, so there is nothing here to
        reword — and inventing an answer from an edit would be its own bug."""
        me = self._device(session, room, "orphanedit")
        assert (
            self._intents(session, room, me, {"edit": {"text": "A rewrite"}})[
                "edit"
            ]
            == outbox.DROP
        )

    def test_an_edit_inside_the_cooldown_is_retried_not_dropped(self, session, room):
        """A rejection that becomes valid in ten seconds must stay queued —
        unlike one that can never succeed."""
        me = self._device(session, room, "cooldown")
        self._intents(session, room, me, {"answer": {"text": "One"}})
        self._intents(session, room, me, {"edit": {"text": "Two"}})
        outcomes = self._intents(session, room, me, {"edit": {"text": "Three"}})
        assert outcomes["edit"] == outbox.RETRY

    # -- support --------------------------------------------------------

    def _two_devices(self, session, room):
        from rhiz.utils.rooms import submit_answer

        mine = self._device(session, room, "supporter")
        theirs = self._device(session, room, "supported")
        submit_answer(session, room, theirs, "Their wording")
        return mine, theirs

    def test_a_queued_support_lands(self, session, room):
        mine, theirs = self._two_devices(session, room)
        self._intents(session, room, mine, {"answer": {"text": "My wording"}})
        outcomes = self._intents(
            session, room, mine, {"support": {"reckoning_id": theirs.current_answer_id}}
        )
        assert outcomes["support"] == outbox.APPLIED
        assert mine.supported_answer_id == theirs.current_answer_id

    def test_replaying_a_support_does_not_vote_twice(self, session, room):
        mine, theirs = self._two_devices(session, room)
        self._intents(session, room, mine, {"answer": {"text": "My wording"}})
        intent = {"support": {"reckoning_id": theirs.current_answer_id}}
        assert self._intents(session, room, mine, intent)["support"] == outbox.APPLIED
        assert self._intents(session, room, mine, intent)["support"] == outbox.ALREADY

        from sqlmodel import select

        from rhiz.state.base import RoomSwap

        swaps = session.exec(
            select(RoomSwap).where(RoomSwap.participant_id == mine.id)
        ).all()
        assert len(swaps) == 1

    def test_supporting_without_having_answered_is_dropped(self, session, room):
        """Support is a move *from* the device's own wording."""
        mine, theirs = self._two_devices(session, room)
        outcomes = self._intents(
            session, room, mine, {"support": {"reckoning_id": theirs.current_answer_id}}
        )
        assert outcomes["support"] == outbox.DROP

    def test_support_for_another_rooms_answer_is_dropped(self, session, room):
        """A queue entry from a previous room must never speak in this one."""
        from rhiz.utils.rooms import create_room, submit_answer

        mine = self._device(session, room, "crossroom")
        elsewhere = create_room(session, "An entirely different question", room.created_by, 60)
        stranger = self._device(session, elsewhere, "stranger")
        submit_answer(session, elsewhere, stranger, "Somewhere else's wording")
        try:
            self._intents(session, room, mine, {"answer": {"text": "Here"}})
            outcomes = self._intents(
                session, room, mine, {"support": {"reckoning_id": stranger.current_answer_id}}
            )
            assert outcomes["support"] == outbox.DROP
            assert mine.supported_answer_id is None
        finally:
            from rhiz.utils.rooms import delete_room

            delete_room(session, elsewhere.id)

    def test_support_for_a_deleted_answer_is_dropped(self, session, room):
        mine, _ = self._two_devices(session, room)
        self._intents(session, room, mine, {"answer": {"text": "Mine"}})
        outcomes = self._intents(
            session, room, mine, {"support": {"reckoning_id": 99_999_999}}
        )
        assert outcomes["support"] == outbox.DROP

    # -- ordering and failures -----------------------------------------

    def test_answer_then_support_apply_in_one_visit(self, session, room):
        """Both tapped while offline: the answer must exist before the swap
        moves it, or the vote is silently lost."""
        mine, theirs = self._two_devices(session, room)
        outcomes = self._intents(
            session,
            room,
            mine,
            {
                "answer": {"text": "My wording"},
                "support": {"reckoning_id": theirs.current_answer_id},
            },
        )
        assert outcomes == {
            "answer": outbox.APPLIED,
            "support": outbox.APPLIED,
        }
        assert mine.supported_answer_id == theirs.current_answer_id

    def test_a_closed_room_drops_the_intent_for_good(self, session, room):
        """Retrying an answer into a closed room can never succeed, so keeping
        it queued would nag the participant for nothing."""
        from rhiz.utils.rooms import close_room

        me = self._device(session, room, "closed")
        close_room(session, room.id)
        outcomes = self._intents(
            session, room, me, {"answer": {"text": "Too late"}}
        )
        assert outcomes["answer"] == outbox.DROP

    def test_an_unreachable_database_keeps_the_intent(self, session, room, monkeypatch):
        """A hiccup is precisely what the queue is for: nothing is lost, and it
        goes again on the next round trip."""
        me = self._device(session, room, "hiccup")
        monkeypatch.setattr(
            outbox, "submit_answer", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down"))
        )
        outcomes = self._intents(
            session, room, me, {"answer": {"text": "Will land later"}}
        )
        assert outcomes["answer"] == outbox.RETRY
