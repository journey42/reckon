"""Data-access helpers for live Q&A rooms.

A room is a Group with ``is_room=True`` (private, unguessable slug). Answers
are Reckoning rows scoped to the room with ``user_id=None``. Anonymous
participation is keyed by a device cookie whose per-room hash lives in
``roomparticipant``.

Auto-close is enforced lazily: every room read/write calls
``enforce_deadline()``, so a room closes as soon as its deadline passes even
if no page is open and no scheduler exists.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import select, func

import reflex as rx

from rhiz.state.base import (
    Group,
    GroupStatus,
    Reckoning,
    ReckoningTypes,
    RoomParticipant,
    RoomSwap,
)
from rhiz.utils.db import find_similar_texts_with_join, insert_text_with_embedding
from rhiz.utils.parsing import remove_html_tags

# Similarity thresholds are cosine distances (lower = stricter).
DEFAULT_SIMILARITY_THRESHOLD = 0.6
THRESHOLD_CHOICES = [
    ("Tight (fewer similar matches)", 0.45),
    ("Balanced", 0.6),
    ("Loose (more similar matches)", 0.7),
]

# Facilitator-selectable durations (minutes); first entry is the default.
DURATION_CHOICES = [15, 30, 60, 90, 120]
DEFAULT_DURATION_MINUTES = 60

EXTEND_MINUTES = 15

# Minimum seconds between edits of the same answer.
EDIT_COOLDOWN_SECONDS = 10

# Hard cap for an anonymous answer.
MAX_ANSWER_LENGTH = 2000


def device_hash_for(device_token: str, room_slug: str) -> str:
    """Per-room hash of the device cookie: identity can't be correlated
    across rooms from the database."""
    return hashlib.sha256(f"{device_token}:{room_slug}".encode()).hexdigest()


def create_room(
    session,
    question: str,
    created_by: int,
    duration_minutes: int = DEFAULT_DURATION_MINUTES,
    similarity_threshold: float | None = None,
) -> Group:
    """Create a live Q&A room: a private group in room mode.

    The founding question is stored both on the group and as the group's
    founding concept (same pattern as a regular group). The slug is an
    unguessable token because the room link is the only public access path.
    """
    question = (question or "").strip()
    if not question:
        raise ValueError("The question is required.")
    if duration_minutes not in DURATION_CHOICES:
        duration_minutes = DEFAULT_DURATION_MINUTES
    if similarity_threshold is None:
        similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD

    def _taken(candidate: str) -> bool:
        return session.exec(select(Group).where(Group.slug == candidate)).first() is not None

    slug = secrets.token_urlsafe(12)
    while _taken(slug):
        slug = secrets.token_urlsafe(12)

    now = datetime.utcnow()
    concept = Reckoning(
        content=question,
        type=ReckoningTypes.concept,
        created_at=now,
        updated_at=now,
        user_id=created_by,
    )
    session.add(concept)
    session.flush()

    group = Group(
        slug=slug,
        concept_id=concept.id,
        name=question[:120],
        founding_question=question,
        status=GroupStatus.open,
        is_public=False,
        created_by=created_by,
        created_at=now,
        is_room=True,
        similarity_threshold=similarity_threshold,
        close_at=now + timedelta(minutes=duration_minutes),
    )
    session.add(group)
    session.flush()

    concept.group_id = group.id
    session.add(concept)
    session.commit()
    session.refresh(group)
    return group


def get_room(session, slug: str) -> Optional[Group]:
    group = session.exec(select(Group).where(Group.slug == slug)).first()
    if group is None or not group.is_room:
        return None
    return group


def enforce_deadline(session, group: Group) -> Group:
    """Close the room if its deadline has passed; return the fresh room.

    Called on every room read/write — this is what makes auto-close work
    without a background scheduler.
    """
    if (
        group.is_room
        and group.status == GroupStatus.open
        and group.close_at is not None
        and group.close_at <= datetime.utcnow()
    ):
        group.status = GroupStatus.closed
        group.closed_at = datetime.utcnow()
        session.add(group)
        session.commit()
        session.refresh(group)
    return group


def extend_room(session, room_id: int, minutes: int = EXTEND_MINUTES) -> Optional[Group]:
    """Push the deadline out while the room is open."""
    group = session.get(Group, room_id)
    if group is None or not group.is_room or group.status != GroupStatus.open:
        return None
    enforce_deadline(session, group)
    if group.status != GroupStatus.open:
        return None
    base = group.close_at or datetime.utcnow()
    if base <= datetime.utcnow():
        base = datetime.utcnow()
    group.close_at = base + timedelta(minutes=minutes)
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


def close_room(session, room_id: int, closing_note: str | None = None) -> Optional[Group]:
    """Close a room immediately (facilitator action), with an optional note."""
    group = session.get(Group, room_id)
    if group is None or not group.is_room or group.status == GroupStatus.closed:
        return None
    group.status = GroupStatus.closed
    group.closed_at = datetime.utcnow()
    note = (closing_note or "").strip()
    group.closing_note = note or None
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


def set_threshold(session, room_id: int, threshold: float) -> Optional[Group]:
    """Adjust the room's similarity threshold while it is open."""
    group = session.get(Group, room_id)
    if group is None or not group.is_room or group.status != GroupStatus.open:
        return None
    group.similarity_threshold = threshold
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


def room_status(session, group: Group) -> dict:
    """What a room page needs to render its current phase (no answers)."""
    group = enforce_deadline(session, group)
    remaining_seconds = 0
    if group.status == GroupStatus.open and group.close_at is not None:
        remaining_seconds = max(
            0, int((group.close_at - datetime.utcnow()).total_seconds())
        )
    return {
        "status": group.status,
        "closing_note": group.closing_note,
        "remaining_seconds": remaining_seconds,
        "close_at": group.close_at,
        "closed_at": group.closed_at,
        "threshold": group.similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD,
    }


def get_or_create_participant(session, group: Group, device_token: str) -> RoomParticipant:
    """Return the roomparticipant row for this device in this room."""
    dhash = device_hash_for(device_token, group.slug)
    participant = session.exec(
        select(RoomParticipant).where(RoomParticipant.device_hash == dhash)
    ).first()
    if participant is None:
        participant = RoomParticipant(room_id=group.id, device_hash=dhash)
        session.add(participant)
        session.commit()
        session.refresh(participant)
    else:
        participant.last_seen_at = datetime.utcnow()
        session.add(participant)
        session.commit()
    return participant


def _withdraw_answer(session, reckoning_id: int) -> None:
    """Withdraw an answer whose author swapped away.

    Tombstoned rather than deleted: the RoomSwap record references it (the
    consolidation story), so the row stays server-side. ``room_results``
    hides it unless other participants had already swapped into it.
    """
    row = session.get(Reckoning, reckoning_id)
    if row is not None and row.removed_at is None:
        row.removed_at = datetime.utcnow()
        session.add(row)


def submit_answer(
    session,
    group: Group,
    participant: RoomParticipant,
    content: str,
) -> tuple[Optional[Reckoning], list[dict]]:
    """Save an anonymous answer. Returns (answer, similar_answers).

    Raises ValueError on invalid submissions (too long, already answered,
    room closed). ``similar_answers`` is a list of {id, content} dicts for the
    private nudge screen, or empty when nothing matched.
    """
    enforce_deadline(session, group)
    if group.status != GroupStatus.open:
        raise ValueError("This question has closed.")
    if participant.current_answer_id is not None:
        raise ValueError("You have already answered this question.")
    if participant.supported_answer_id is not None:
        raise ValueError("You already chose to support another participant's answer.")
    content = (content or "").strip()
    if not content:
        raise ValueError("Write an answer before submitting.")
    if len(content) > MAX_ANSWER_LENGTH:
        raise ValueError(f"Answers are limited to {MAX_ANSWER_LENGTH} characters.")

    now = datetime.utcnow()
    answer = Reckoning(
        content=content,
        type=ReckoningTypes.concept,
        created_at=now,
        updated_at=now,
        user_id=None,
        group_id=group.id,
    )
    session.add(answer)
    session.commit()

    cleaned = remove_html_tags(content)
    insert_text_with_embedding(cleaned, answer.id)

    participant.current_answer_id = answer.id
    participant.last_seen_at = now
    session.add(participant)
    session.commit()

    threshold = group.similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD
    similar_keys, _ = find_similar_texts_with_join(
        answer.id, threshold, 10, group_id=group.id
    )
    similar_rows: list[dict] = []
    for sid in similar_keys:
        if sid == answer.id:
            continue
        row = session.get(Reckoning, sid)
        if row is not None and row.removed_at is None:
            similar_rows.append({"id": row.id, "content": row.content})
    return answer, similar_rows


def edit_answer(
    session,
    group: Group,
    participant: RoomParticipant,
    content: str,
) -> Optional[Reckoning]:
    """Edit the device's own answer while the room is open.

    Returns the updated answer, or None on rejection (cooldown, closed,
    not the owner).
    """
    enforce_deadline(session, group)
    if group.status != GroupStatus.open:
        raise ValueError("This question has closed.")
    if participant.current_answer_id is None:
        return None
    answer = session.get(Reckoning, participant.current_answer_id)
    if answer is None or answer.removed_at is not None:
        return None

    content = (content or "").strip()
    if not content:
        raise ValueError("The answer cannot be empty.")
    if len(content) > MAX_ANSWER_LENGTH:
        raise ValueError(f"Answers are limited to {MAX_ANSWER_LENGTH} characters.")

    last_touch = answer.edited_at or answer.created_at or datetime.utcnow()
    if datetime.utcnow() - last_touch < timedelta(seconds=EDIT_COOLDOWN_SECONDS):
        raise ValueError("Please wait a few seconds between edits.")

    answer.content = content
    answer.updated_at = datetime.utcnow()
    answer.edited_at = answer.updated_at
    session.add(answer)
    session.commit()

    insert_text_with_embedding(remove_html_tags(content), answer.id)
    session.refresh(answer)
    return answer


def swap_support(
    session,
    group: Group,
    participant: RoomParticipant,
    to_reckoning_id: int,
) -> bool:
    """Move the device's support from their wording to another answer.

    Records a RoomSwap (the consolidation story), withdraws the original
    wording (hidden from results; it stays server-side because the swap
    record references it, and it keeps rendering only if other participants
    had already swapped into it) and records the new support. The device
    cannot submit again afterwards.
    """
    enforce_deadline(session, group)
    if group.status != GroupStatus.open:
        raise ValueError("This question has closed.")
    if participant.supported_answer_id is not None:
        return False
    if participant.current_answer_id is None:
        return False

    mine_id = participant.current_answer_id
    target = session.get(Reckoning, to_reckoning_id)
    if (
        target is None
        or target.removed_at is not None
        or target.group_id != group.id
        or target.id == mine_id
    ):
        return False

    now = datetime.utcnow()
    swap = RoomSwap(
        room_id=group.id,
        participant_id=participant.id,
        from_reckoning_id=mine_id,
        to_reckoning_id=target.id,
        created_at=now,
    )
    session.add(swap)

    # Withdraw the original wording: tombstone it (the swap record references
    # it, so the row must stay). Rendering in room_results hides withdrawn
    # answers unless other participants consolidated into them.
    _withdraw_answer(session, mine_id)

    participant.current_answer_id = None
    participant.supported_answer_id = target.id
    participant.last_seen_at = now
    session.add(participant)
    session.commit()
    return True


def my_answer(session, participant: RoomParticipant) -> Optional[Reckoning]:
    """The device's live answer, if any."""
    if participant.current_answer_id is None:
        return None
    answer = session.get(Reckoning, participant.current_answer_id)
    if answer is None or answer.removed_at is not None:
        return None
    return answer


def room_results(session, group: Group) -> dict:
    """Final ranked results for the closed room (the artifact).

    support = (1 if the author has not swapped away else 0) + swaps in.
    Answers withdrawn with zero inbound swaps were deleted at swap time and
    simply don't appear. Removed answers render as tombstones at rank.
    """
    rows = session.exec(
        select(Reckoning)
        .where(
            Reckoning.group_id == group.id,
            Reckoning.type == ReckoningTypes.concept,
            Reckoning.id != group.concept_id,
        )
        .order_by(Reckoning.created_at.asc())
    ).all()

    swap_counts: dict[int, int] = {}
    for rid, cnt in session.exec(
        select(RoomSwap.to_reckoning_id, func.count(RoomSwap.id))
        .where(RoomSwap.room_id == group.id)
        .group_by(RoomSwap.to_reckoning_id)
    ).all():
        swap_counts[rid] = cnt

    still_authored = {
        p.current_answer_id
        for p in session.exec(
            select(RoomParticipant).where(RoomParticipant.room_id == group.id)
        ).all()
        if p.current_answer_id is not None
    }

    items = []
    for r in rows:
        swaps_in = swap_counts.get(r.id, 0)
        support = (1 if r.id in still_authored else 0) + swaps_in
        if r.removed_at is not None:
            if swaps_in == 0:
                # Withdrawn by its author, nobody consolidated into it:
                # never renders anywhere.
                continue
            # Tombstone (facilitator/admin removal, or withdrawn-but-merged):
            # render the marker at its ranked position, never the content.
            items.append(
                {
                    "id": r.id,
                    "content": "",
                    "support": 0,
                    "swaps_in": swaps_in,
                    "edited": False,
                    "removed": True,
                    "created_at": r.created_at,
                }
            )
            continue
        items.append(
            {
                "id": r.id,
                "content": r.content,
                "support": support,
                "swaps_in": swaps_in,
                "has_swaps": swaps_in > 0,
                "swaps_text": f"· {swaps_in} switched to this" if swaps_in else "",
                "edited": r.edited_at is not None,
                "removed": False,
                "created_at": r.created_at,
            }
        )
    items.sort(key=lambda x: (-x["support"], x["created_at"]))

    group = enforce_deadline(session, group)
    return {
        "status": group.status,
        "closing_note": group.closing_note,
        "items": items,
        "total_swaps": sum(swap_counts.values()),
        "total_answers": len(items),
    }


def remove_answer_admin(session, reckoning_id: int) -> bool:
    """Post-close admin removal: tombstone the answer, keep rank position."""
    row = session.get(Reckoning, reckoning_id)
    if row is None or row.group_id is None:
        return False
    group = session.get(Group, row.group_id)
    if group is None or not group.is_room:
        return False
    row.removed_at = datetime.utcnow()
    session.add(row)
    session.commit()
    return True
