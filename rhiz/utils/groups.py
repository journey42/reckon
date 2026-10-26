"""Data-access helpers for group pages."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import select

from rhiz.state.base import (
    Group,
    GroupStatus,
    GroupMember,
    Reckoning,
    ReckoningTypes,
    User,
    UserTypes,
    get_setting,
)
from rhiz.utils.slugs import slugify, unique_slug


def founding_text(session, group: Optional[Group]) -> str:
    """The question a group is built around, however this row happens to store it.

    New groups keep the wording on the ``group`` row *and* as their founding
    concept. Rows written before that column existed — and any written by a path
    that populated only one of the two — have the text on the concept alone,
    which is where ``concept_id`` points. Falling back to it costs one lookup and
    is why a group page never has to show an empty "Your group has asked:".

    Returns "" only when neither place has anything, which is a row worth
    looking at: ``scripts/backfill_founding_questions.py`` reports those.
    """
    if group is None:
        return ""
    text = (group.founding_question or "").strip()
    if text:
        return text
    if group.concept_id:
        concept = session.get(Reckoning, group.concept_id)
        if concept is not None:
            return (concept.content or "").strip()
    return ""

# Self-service group creation is a client-requested safeguard: new accounts get
# the grant automatically, but creation is bounded by an admin toggle and a
# rolling 24h quota shared by groups *and* live rooms (a room is a group, so
# capping only one of the two would leave the other wide open).
AUTO_GROUP_CREATION_SETTING = "auto_group_creation_enabled"
GROUP_DAILY_LIMIT_SETTING = "group_creation_daily_limit"
DEFAULT_GROUP_DAILY_LIMIT = 3
_GROUP_QUOTA_WINDOW_HOURS = 24


def _utcnow_naive() -> datetime:
    """Naive UTC now.

    ``group.created_at`` is a timestamp *without* time zone holding UTC wall
    time, so the cutoff has to be naive too: comparing it against an aware
    datetime makes Postgres reinterpret every stored row in the session time
    zone, which on a -07:00 box quietly ages the 24h window by seven hours.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def auto_group_creation_enabled() -> bool:
    """Whether new accounts are granted group creation automatically.

    Defaults to on: switching it off is an admin intervention, not a default.
    """
    return get_setting(AUTO_GROUP_CREATION_SETTING, "true").strip().lower() != "false"


def group_creation_daily_limit() -> int:
    """Groups + rooms one account may create per rolling 24h. 0 pauses creation.

    Unset, blank or unparseable all fall back to the default, so a typo in the
    admin UI cannot silently mean "unlimited".
    """
    raw = get_setting(GROUP_DAILY_LIMIT_SETTING, "").strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_GROUP_DAILY_LIMIT


def check_group_creation_quota(
    session, user, require_permission: bool = True
) -> tuple[bool, str]:
    """May ``user`` create another group (or room) right now?

    Returns ``(ok, message)``; ``message`` is what to show the user when the
    answer is no. ``require_permission=False`` is the live-room path: opening a
    room has never needed the ``can_create_groups`` grant, but the quota still
    applies there.
    """
    if user is None:
        return False, "Please log in first."

    is_admin = user.role >= UserTypes.admin
    if require_permission and not is_admin and not user.can_create_groups:
        return False, (
            "Your account does not have group-creation permission yet. "
            "Ask an administrator to enable it."
        )

    if not user.enabled:
        return False, (
            "Verify your email address first — use the link we emailed you "
            "before creating a group."
        )

    limit = group_creation_daily_limit()
    if limit <= 0:
        return False, (
            "Group creation is paused for new accounts right now. Please try "
            "again later."
        )

    cutoff = _utcnow_naive() - timedelta(hours=_GROUP_QUOTA_WINDOW_HOURS)
    recent = session.exec(
        select(Group).where(Group.created_by == user.id, Group.created_at > cutoff)
    ).all()
    if len(recent) >= limit:
        return False, (
            f"You have reached the limit of {limit} new group"
            f"{'s' if limit != 1 else ''} or live room"
            f"{'s' if limit != 1 else ''} per 24 hours. Please try again later."
        )

    return True, ""


def get_group_by_slug(session, slug: str):
    return session.exec(select(Group).where(Group.slug == slug)).first()


def get_group_for_concept(session, concept_id: int):
    return session.exec(select(Group).where(Group.concept_id == concept_id)).first()


def create_group(session, name: str, founding_question: str, created_by: int):
    """Create a group from scratch.

    A group has its own founding question (stored as a concept scoped to the
    group via group_id) and serves as a container for user-submitted concepts.

    The question is required here, not just in the dialog: a blank founding
    question would create a group whose header is empty and whose founding
    concept is empty, and neither the read fallback nor the backfill can
    recover it. That is the failure mode the client reported.
    """
    name = (name or "").strip()
    founding_question = (founding_question or "").strip()
    if not name:
        raise ValueError("Group name is required.")
    if not founding_question:
        raise ValueError("Founding question is required.")

    def _taken(candidate: str) -> bool:
        return get_group_by_slug(session, candidate) is not None

    slug = unique_slug(slugify(name), _taken)
    now = datetime.now(timezone.utc)
    concept = Reckoning(
        content=founding_question or "",
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
        name=name,
        founding_question=founding_question or "",
        status=GroupStatus.open,
        is_public=False,
        created_by=created_by,
    )
    session.add(group)
    session.flush()

    # Scope the founding concept to this group
    concept.group_id = group.id
    session.commit()
    session.refresh(group)

    # Audit row: group creation was previously unlogged, so the client had
    # no record of new groups (counts + timestamps only; no content).
    from rhiz.state.base import Log

    session.add(
        Log(
            user_id=created_by,
            content=f"created group {group.id}",
            type="group",
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    # Capture PostHog event for group creation.
    from rhiz.utils.telemetry import GROUP_CREATED, capture

    capture(
        GROUP_CREATED,
        distinct_id=f"user-{created_by}",
        group_id=group.id,
        group_slug=group.slug,
        created_by=created_by,
        name_length=len(name),
        is_room=bool(getattr(group, "is_room", False)),
    )

    return group


def set_group_status(session, group_id: int, status: str) -> None:
    group = session.exec(select(Group).where(Group.id == group_id)).first()
    if group is not None:
        group.status = status
        session.commit()


def set_group_public(session, group_id: int, is_public: bool) -> None:
    group = session.exec(select(Group).where(Group.id == group_id)).first()
    if group is not None:
        group.is_public = is_public
        session.commit()


def delete_group(session, group_id: int, owner_id: int | None = None) -> None:
    """Delete a group and all its concepts, comments, votes, and memberships.

    Handles the circular FK: group.concept_id → reckoning.id (NOT NULL) AND
    reckoning.group_id → group.id (nullable).  We null out group_id on all
    affected reckonings first, then delete the group, then delete the
    reckonings.

    Everything runs in a single transaction: a failure (e.g. a leftover
    membership blocking the group delete) rolls back all steps, so a
    half-deleted group can never leak its founding concept onto the
    site-wide feed.
    """
    group = session.exec(select(Group).where(Group.id == group_id)).first()
    if group is None:
        return
    if owner_id is not None and group.created_by != owner_id:
        return
    # A live Q&A room must never be deleted this way: nulling group_id would
    # publish its anonymous answers site-wide. Hand off to the room-aware
    # helper, which deletes the content with the room.
    if group.is_room:
        from rhiz.utils.rooms import delete_room

        delete_room(session, group_id, owner_id=owner_id)
        return
    from sqlalchemy import delete as sa_delete, text

    concept_id = group.concept_id

    try:
        # Step 1: Remove group memberships (FK blocks the group delete
        # otherwise — this is what made deletes fail before).
        session.execute(
            sa_delete(GroupMember).where(GroupMember.group_id == group_id)
        )

        # Step 2: Null out reckoning.group_id for all group-scoped
        # reckonings so the group row can be deleted (breaks
        # reckoning→group FK).
        session.execute(
            text("UPDATE reckoning SET group_id = NULL WHERE group_id = :gid"),
            {"gid": group_id},
        )

        # Step 3: Delete the group row (concept_id FK still references the
        # founding concept, but group→reckoning direction is fine).
        # Flush explicitly: raw SQL below does not trigger autoflush.
        session.delete(group)
        session.flush()

        # Step 4: Delete all the reckonings — the founding concept and all
        # its descendants (comments, votes, sub-concepts).
        session.execute(
            text(
                """
                WITH RECURSIVE descendants AS (
                    SELECT :concept_id AS id
                    UNION ALL
                    SELECT r.id FROM reckoning r
                    JOIN descendants d ON r.parent_reckoning_id = d.id
                )
                DELETE FROM reckoning WHERE id IN (SELECT id FROM descendants)
                """
            ),
            {"concept_id": concept_id},
        )

        session.commit()
    except Exception:
        session.rollback()
        raise

    session.expire_all()


def update_group_details(
    session,
    group_id: int,
    owner_id: int | None = None,
    name: str | None = None,
    founding_question: str | None = None,
) -> Optional[Group]:
    """Update a group's name and/or founding question (headline).

    Keeps the founding concept's content in sync with the founding question.
    Only the group's creator (or an admin, via owner_id=None) may call this.
    Returns the updated group, or None if not found / not authorised.
    """
    group = session.exec(select(Group).where(Group.id == group_id)).first()
    if group is None:
        return None
    if owner_id is not None and group.created_by != owner_id:
        return None
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            return None
        group.name = cleaned
    if founding_question is not None:
        cleaned = founding_question.strip()
        if not cleaned:
            # Empty is not a valid edit: it writes "" over both the column and
            # the founding concept, so the read fallback has nothing to recover
            # and the group header goes blank for good.
            raise ValueError("Founding question is required.")
        group.founding_question = cleaned
        concept = session.exec(
            select(Reckoning).where(Reckoning.id == group.concept_id)
        ).first()
        if concept is not None:
            concept.content = cleaned
            concept.updated_at = datetime.now(timezone.utc)
            session.add(concept)
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


# ── Group membership helpers ──────────────────────────────────────────

def get_membership(session, user_id: int, group_id: int) -> Optional[GroupMember]:
    """Return the membership row for a user+group, or None."""
    return session.exec(
        select(GroupMember).where(
            GroupMember.user_id == user_id,
            GroupMember.group_id == group_id,
        )
    ).first()


def is_member(session, user_id: int, group_id: int) -> bool:
    """Check if a user is a member of a group."""
    return get_membership(session, user_id, group_id) is not None


def join_group(session, user_id: int, group_id: int) -> Optional[GroupMember]:
    """Add a user to a group. Returns the membership (new or existing)."""
    from rhiz.state.base import Log

    existing = get_membership(session, user_id, group_id)
    if existing:
        return existing
    member = GroupMember(user_id=user_id, group_id=group_id)
    session.add(member)
    session.commit()
    session.refresh(member)

    # Audit row: membership joins were previously invisible — the client had
    # no record of who joined what, when. Counts + timestamps only; content
    # stays private to the group.
    session.add(
        Log(
            user_id=user_id,
            content=f"joined group {group_id}",
            type="group_join",
            created_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    # Telemetry: member_joined fired for every join.
    from rhiz.utils.telemetry import MEMBER_JOINED, capture

    group = session.get(Group, group_id)
    capture(
        MEMBER_JOINED,
        distinct_id=f"user-{user_id}",
        group_id=group_id,
        group_slug=group.slug if group is not None else None,
    )

    return member


def leave_group(session, user_id: int, group_id: int) -> bool:
    """Remove a user from a group. Returns True if a row was deleted."""
    member = get_membership(session, user_id, group_id)
    if member is None:
        return False
    session.delete(member)
    session.commit()
    return True


def add_member_by_email(session, email: str, group_id: int) -> Optional[GroupMember]:
    """Find a user by email and add them to a group.

    Returns the membership row on success, or None if the user was not found.
    """
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        return None
    return join_group(session, user.id, group_id)


def get_group_members(session, group_id: int) -> list[dict]:
    """Return a list of {id, username, email, joined_at} for all members."""
    rows = session.exec(
        select(GroupMember, User.username, User.email)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at)
    ).all()
    return [
        {
            "id": m.id,
            "user_id": m.user_id,
            "username": username,
            "email": email,
            "joined_at": m.joined_at,
        }
        for m, username, email in rows
    ]


def remove_member(session, member_id: int) -> bool:
    """Remove a specific membership by its ID."""
    member = session.exec(select(GroupMember).where(GroupMember.id == member_id)).first()
    if member is None:
        return False
    session.delete(member)
    session.commit()
    return True
