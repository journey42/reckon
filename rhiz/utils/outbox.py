"""The live-room outbox: participant writes held on the device until they land.

Why this exists: at a conference with ~300 people on one access point, a phone
cannot ask a server it cannot reach to remember anything. So the queue has to
live in the browser (``assets/outbox.js`` writes it, the server only ever
receives the pending intents for the room currently open), and the page has to
be able to replay them — including after its own 20-second auto-reload, which
destroys all in-memory state.

The one design decision that makes replay safe: **intents are desired states,
not commands.** An intent says "this device's answer is this text", not "create
an answer". Applying an intent twice is therefore identical to applying it
once, so a write that actually reached the server before the connection dropped
— and gets replayed from the queue minutes later — cannot produce a duplicate
answer, a second swap, or a lost vote. That is also why there are no intent ids
and no dedup ledger: there is nothing to deduplicate.

The browser is untrusted, so everything crossing the boundary is re-validated
here (shape, length, age, slug format) and malformed entries are dropped rather
than raising: a queue entry the server cannot understand must not be able to
break the page for the person who made it, or 400 for everybody else.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from rhiz.state.base import Group, Reckoning, RoomParticipant
from rhiz.utils.rooms import edit_answer, submit_answer, swap_support

# The three things a participant can do in a room, in the order they compose:
# answer first, then reword it, then support someone else's wording (which
# withdraws yours). Applying them out of order would swap the semantics.
KIND_ANSWER = "answer"
KIND_EDIT = "edit"
KIND_SUPPORT = "support"
KINDS = (KIND_ANSWER, KIND_EDIT, KIND_SUPPORT)

# localStorage key shared with assets/outbox.js. Bump the suffix if the shape
# changes so stale blobs from an older build are ignored rather than parsed.
OUTBOX_STORAGE_KEY = "rhiz_room_outbox_v2"

# An intent older than this is not a retry, it is debris: the room it belongs to
# closed long ago. Dropping it also stops a months-old queued answer from
# landing in a brand-new room that happens to reuse a slug.
MAX_INTENT_AGE_MINUTES = 30

# A little forward tolerance, because ``at`` is stamped by the device's clock
# and phones disagree with servers by minutes routinely.
MAX_CLOCK_SKEW_MINUTES = 10

MAX_TEXT_CHARS = 2000
MAX_SLUG_CHARS = 64
MAX_PAYLOAD_CHARS = 64_000
_SLUG_RE = re.compile(r"^[A-Za-z0-9_-]{1,%d}$" % MAX_SLUG_CHARS)

# Outcomes per intent. RETRY is the only one that keeps the entry queued.
APPLIED = "applied"  # the write landed now
ALREADY = "already"  # it had already landed (replay) — nothing to do
RETRY = "retry"  # transient: cooldown, closed race, provider hiccup
DROP = "drop"  # will never succeed (stale intent, room closed, bad entry)

_OUTCOME_KEYS = {APPLIED, ALREADY, RETRY, DROP}


def _utcnow_naive() -> datetime:
    """Naive UTC: the room tables store naive UTC timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def decode_intents(payload: Any) -> dict[str, dict[str, Any]]:
    """Validate the JSON the browser sent for *this* room.

    Returns ``{kind: intent}`` containing only well-formed, unexpired intents,
    ordered by :data:`KINDS`. Anything else is silently dropped: the caller must
    never have to handle an exception from someone else's localStorage.
    """
    if not isinstance(payload, str) or not payload or len(payload) > MAX_PAYLOAD_CHARS:
        return {}
    try:
        raw = json.loads(payload)
    except (ValueError, TypeError):
        return {}
    if not isinstance(raw, dict):
        return {}

    now = _utcnow_naive()
    newest = now + timedelta(minutes=MAX_CLOCK_SKEW_MINUTES)
    oldest = now - timedelta(minutes=MAX_INTENT_AGE_MINUTES)

    out: dict[str, dict[str, Any]] = {}
    for kind in KINDS:
        entry = raw.get(kind)
        if not isinstance(entry, dict):
            continue
        intent = _normalise(kind, entry, oldest, newest)
        if intent is not None:
            out[kind] = intent
    # Preserve the canonical order even though dict iteration is insertion
    # ordered, so callers can rely on it without knowing how we built it.
    return {kind: out[kind] for kind in KINDS if kind in out}


def _normalise(
    kind: str, entry: dict, oldest: datetime, newest: datetime
) -> Optional[dict]:
    """Normalise one entry and check its age, or None if it cannot be trusted.

    Entries fail closed. This JSON was authored by a browser we do not trust —
    it may be stale, truncated by a full localStorage, or typed by hand into dev
    tools — so anything we cannot make sense of is dropped instead of applied.
    """
    if kind in (KIND_ANSWER, KIND_EDIT):
        text = entry.get("text")
        if not isinstance(text, str):
            return None
        text = text.strip()
        if not text or len(text) > MAX_TEXT_CHARS:
            return None
        intent = {"text": text}
    else:
        target = entry.get("reckoning_id")
        if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
            return None
        intent = {"reckoning_id": target}

    # ``at`` is milliseconds since the epoch, stamped in the browser. An intent
    # we cannot date is an intent we cannot bound, so it goes.
    stamp = entry.get("at")
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
        return None
    try:
        when = datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).replace(
            tzinfo=None
        )
    except (OverflowError, OSError, ValueError):
        return None
    if when < oldest or when > newest:
        return None

    # Server-issued revision: the browser sends the version it believes is
    # current. Absent means a legacy/older blob and is treated as "apply", but
    # a version at or below the server's current one is a replay or a
    # superseded write and is decided without touching the row.
    version = entry.get("version")
    if version is not None:
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            return None
        intent["version"] = version
    return intent


def clear_intents_js(kinds: list[str] | None = None, version: int | None = None) -> str:
    """JS that removes applied intents and syncs the revision.

    The server cannot write the browser's localStorage, so it tells the browser
    to do it — this is the only way a completed write stops showing as pending,
    and the revision is how the device learns which intents are now stale.
    """
    wanted = [k for k in (kinds or list(KINDS)) if k in set(KINDS) | {"draft"}]
    payload = json.dumps(wanted)
    js = f"window.rhizOutboxClear&&window.rhizOutboxClear({payload});"
    if version is not None:
        js += f"window.rhizOutboxVersion&&window.rhizOutboxVersion({int(version)});"
    return js


def apply_intents(
    session,
    room: Group,
    participant: RoomParticipant,
    intents: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Bring the device's server state up to what the queue says it should be.

    Returns ``{kind: outcome}`` using the outcome constants above. Each intent is
    decided against current state rather than executed blindly, which is what
    makes replay harmless:

    * an answer whose text already matches is ``ALREADY`` (the original write
      did land — the connection died on the response, not the request);
    * an answer that differs from the one on file is ``DROP``: somebody (this
      device, a moment ago) already replaced it, and overwriting that silently
      would lose a newer intent for an older one;
    * an edit rejected by the edit cooldown is ``RETRY`` — it becomes valid a
      few minutes later;
    * support for an answer other than the one currently supported is ``DROP``:
      the device has expressed a newer opinion than this queue entry.

    Nothing here raises; a failure becomes ``RETRY`` so the caller keeps the
    entry and tries again on the next round trip.
    """
    results: dict[str, str] = {}
    for kind in KINDS:
        intent = intents.get(kind)
        if intent is None:
            continue
        try:
            results[kind] = _apply_one(session, room, participant, kind, intent)
        except ValueError as exc:
            # ValueError from the room utils means "rejected", which is almost
            # always permanent (closed room, not the owner, length). Keeping it
            # queued would retry something that can never succeed.
            results[kind] = RETRY if _is_transient(str(exc)) else DROP
        except Exception:
            # Anything else (dead connection, timeout) is exactly what the queue
            # is for: keep it and try again.
            results[kind] = RETRY
    return results


def _is_transient(message: str) -> bool:
    """Rejected now versus rejected forever.

    The distinction decides whether the participant's words survive this round
    trip, so the permanent cases are the ones to be careful about: a closed room
    or an over-long answer will fail identically a minute from now, and keeping
    it queued only delays telling them.
    """
    lowered = message.lower()
    return any(
        phrase in lowered
        for phrase in (
            "try again",
            "later",
            "cooldown",
            "temporarily",
            "moment",
            # The edit throttle: "Please wait a few seconds between edits."
            "wait a few seconds",
        )
    )


def _apply_one(session, room, participant, kind: str, intent: dict) -> str:
    """Apply one intent, using the server revision to reject stale writes.

    ``version`` is the revision the browser believed was current when it queued
    the intent. If the server has already reached or passed that revision, the
    intent is either a replay of a write that landed (and the desired state
    already matches) or an older write that a newer one superseded. Either way
    it must not be applied again: doing so would overwrite the newer wording.

    An intent without a version (an older stored blob) is treated as new and
    applied as before; the revision then advances so later intents align.
    """
    current = participant.intent_version or 0
    version = intent.get("version")
    if version is not None and version <= current:
        return ALREADY if _settled_state(session, participant, kind, intent) else DROP

    outcome = _apply_kind(session, room, participant, kind, intent)
    if outcome == APPLIED or (outcome == ALREADY and version is not None):
        participant.intent_version = (
            max(current, version) if version is not None else current + 1
        )
        session.add(participant)
        session.commit()
    return outcome


def _settled_state(session, participant, kind: str, intent: dict) -> bool:
    """Does current server state already say what this intent says?"""
    if kind == KIND_SUPPORT:
        return participant.supported_answer_id == intent["reckoning_id"]
    existing = _current_answer(session, participant)
    return existing is not None and existing.content.strip() == intent["text"]


def _apply_kind(session, room, participant, kind: str, intent: dict) -> str:
    if kind == KIND_ANSWER:
        return _apply_answer(session, room, participant, intent["text"])
    if kind == KIND_EDIT:
        return _apply_edit(session, room, participant, intent["text"])
    return _apply_support(session, room, participant, intent["reckoning_id"])


def _current_answer(session, participant) -> Optional[Reckoning]:
    if participant.current_answer_id is None:
        return None
    return session.get(Reckoning, participant.current_answer_id)


def _apply_answer(session, room, participant, text: str) -> str:
    existing = _current_answer(session, participant)
    if existing is not None:
        return ALREADY if existing.content.strip() == text else DROP
    answer, _similar = submit_answer(session, room, participant, text)
    return APPLIED if answer is not None else DROP


def _apply_edit(session, room, participant, text: str) -> str:
    existing = _current_answer(session, participant)
    if existing is None:
        # Without an answer there is nothing to reword, and an edit intent that
        # follows a lost answer is stale by definition.
        return DROP
    if existing.content.strip() == text:
        return ALREADY
    updated = edit_answer(session, room, participant, text)
    return APPLIED if updated is not None else RETRY


def _apply_support(session, room, participant, reckoning_id: int) -> str:
    if participant.supported_answer_id is not None:
        return ALREADY if participant.supported_answer_id == reckoning_id else DROP
    if participant.current_answer_id is None:
        # Swapping support is a move *from* the device's own wording; a device
        # with no answer has nothing to move.
        return DROP
    target = session.get(Reckoning, reckoning_id)
    if target is None or target.group_id != room.id:
        # The answer was deleted, or the id belongs to another room: never let a
        # stale queue entry express support somewhere it was never shown.
        return DROP
    return APPLIED if swap_support(session, room, participant, reckoning_id) else DROP


def pending_count(intents: dict[str, dict[str, Any]]) -> int:
    return len(intents)
