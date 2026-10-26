"""Permanent Q&A: the questions that live at ``/demo`` and never close.

A demo question is an ordinary live Q&A room with no deadline — ``close_at`` is
NULL, which is the only thing separating it from a room created at a conference.
Keeping it that way means the whole Q&A engine (anonymous participants, the
similarity nudge, support-and-swap, ranking) is *the same code* rather than a
second implementation that drifts from the first.

Which question ``/demo`` displays is a single row in ``appsetting``, so the
facilitator can switch audiences without a deploy, and each question keeps
accumulating its own answer history whether or not it is the one on screen.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import func, select

from rhiz.state.base import (
    AppSetting,
    Group,
    GroupStatus,
    Reckoning,
    RoomParticipant,
)
from rhiz.utils.rooms import DEFAULT_SIMILARITY_THRESHOLD, create_room, room_results

# Where the pointer to the question currently shown at /demo is kept. A slug
# rather than an id so that a database restore between environments keeps
# pointing at a question by name instead of at whatever row happens to share
# the old id.
DEMO_ROOM_SETTING = "demo_room_slug"

# How many answers /demo shows before "show more". The client asked for the top
# five: a first screen full of answers invites reading, a wall of them does not.
ANSWERS_ABOVE_THE_FOLD = 5


def create_demo_question(
    session,
    question: str,
    created_by: int,
    similarity_threshold: float | None = None,
) -> Group:
    """Create a Q&A that never closes.

    Same as ``create_room`` minus the timer: demo answers are worth keeping for
    months, and a room that auto-closes overnight is not a thing to print on a
    card.
    """
    room = create_room(
        session,
        question,
        created_by,
        similarity_threshold=similarity_threshold,
        permanent=True,
    )
    # The first question created is the one shown until someone says otherwise;
    # without this the page would be empty until an admin notices a dropdown.
    if not read_active_slug(session):
        write_active_slug(session, room.slug)
    return room


def is_demo_question(room: Optional[Group]) -> bool:
    """A room with no deadline is a demo question.

    Ordinary rooms always get a ``close_at`` (``create_room`` computes one from
    the chosen duration), so "open forever" is a complete and honest
    definition — no extra flag to keep in step with reality.
    """
    return bool(room and room.is_room and room.close_at is None)


def list_demo_questions(session) -> list[dict]:
    """Every permanent question, newest first, with what it has gathered."""
    rows = session.exec(
        select(Group)
        .where(Group.is_room == True)  # noqa: E712
        .where(Group.close_at == None)  # noqa: E711
        .order_by(Group.created_at.desc())
    ).all()
    counts = dict(
        session.exec(
            # Count answers exactly as /live does: the founding question is a
            # type-0 reckoning too, and soft-deleted answers do not count.
            select(Reckoning.group_id, func.count(Reckoning.id))
            .join(Group, Group.id == Reckoning.group_id)
            .where(
                Reckoning.type == 0,
                Reckoning.removed_at == None,  # noqa: E711
                Reckoning.id != Group.concept_id,
            )
            .group_by(Reckoning.group_id)
        ).all()
    )
    supporters = dict(
        session.exec(
            select(RoomParticipant.room_id, func.count(RoomParticipant.id))
            .where(RoomParticipant.current_answer_id != None)  # noqa: E711
            .group_by(RoomParticipant.room_id)
        ).all()
    )
    slug = read_active_slug(session)
    active = (
        session.exec(select(Group).where(Group.slug == slug)).first() if slug else None
    )
    return [
        {
            "id": room.id,
            "slug": room.slug,
            "question": room.founding_question,
            "created_by": room.created_by,
            "answers": counts.get(room.id, 0),
            "answering": supporters.get(room.id, 0),
            "closed": room.status != GroupStatus.open,
            "is_active": bool(active and active.id == room.id),
        }
        for room in rows
    ]


def demo_question_by_slug(
    session, slug: str, require_open: bool = False
) -> Optional[Group]:
    """The permanent question living at this address, or None.

    Deliberately does not insist it is the *active* one: ``/demo/<slug>`` exists
    so one audience can be handed a link while another audience is pointed at a
    different question, and answers keep landing on the question they were
    written for.

    ``require_open=True`` is the public page's view: a closed question must not
    keep inviting answers, so it degrades to "no question set up yet" rather
    than showing a form whose submit will always be rejected.
    """
    room = session.exec(select(Group).where(Group.slug == slug)).first()
    if not is_demo_question(room):
        return None
    if require_open and room.status != GroupStatus.open:
        return None
    return room


def read_active_slug(session) -> str:
    """Which question /demo points at.

    Read through the caller's session rather than ``get_setting``, which opens
    its own: these helpers are called while the page already holds one open.
    """
    row = session.exec(select(AppSetting).where(AppSetting.key == DEMO_ROOM_SETTING)).first()
    return row.value if row else ""


def write_active_slug(session, slug: str) -> None:
    row = session.exec(select(AppSetting).where(AppSetting.key == DEMO_ROOM_SETTING)).first()
    if row:
        row.value = slug
        session.add(row)
    else:
        session.add(AppSetting(key=DEMO_ROOM_SETTING, value=slug))
    session.commit()


def set_active_demo_question(session, slug: str) -> bool:
    """Point /demo at one of the permanent questions.

    Only an open one: the public resolver (``active_demo_question``) skips
    closed questions, so writing a closed slug would produce a "Saved" message
    for a page that then shows something else. Reopen first.
    """
    room = session.exec(select(Group).where(Group.slug == slug)).first()
    if not is_demo_question(room) or room.status != GroupStatus.open:
        return False
    write_active_slug(session, slug)
    return True


def active_demo_question(session) -> Optional[Group]:
    """The question /demo should render, or None when none exists yet.

    A stale pointer (question deleted, or a database restored from a backup
    that predates it) falls back to the most recent permanent question rather
    than to a broken page: the printed card cannot be changed after the fact.
    """
    slug = read_active_slug(session)
    if slug:
        room = session.exec(select(Group).where(Group.slug == slug)).first()
        if is_demo_question(room) and room.status == GroupStatus.open:
            return room
    fallback = session.exec(
        select(Group)
        .where(Group.is_room == True)  # noqa: E712
        .where(Group.close_at == None)  # noqa: E711
        .where(Group.status == GroupStatus.open)
        .order_by(Group.created_at.desc())
    ).first()
    return fallback


def visible_answers(session, room: Group, limit: int, offset: int = 0) -> dict:
    """Ranked answers for the page: ``limit`` of them, plus whether more exist.

    Ranking is ``room_results`` — support first, then age — because the demo is
    meant to show what the group believes, which is the same ordering the live
    rooms use.
    """
    ranked = [item for item in room_results(session, room)["items"] if not item["removed"]]
    for item in ranked:
        # Decided here, where ``support`` is still a Python int: a page cannot
        # compare a Reflex item var against a number at compile time, and
        # "is this answer supported at all" is the page's only use for it.
        item["hot"] = item["support"] > 0
    return {
        "items": ranked[offset : offset + limit],
        "total": len(ranked),
        "has_more": len(ranked) > offset + limit,
        "offset": offset,
    }
