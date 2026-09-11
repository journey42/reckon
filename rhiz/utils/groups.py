"""Data-access helpers for group pages."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import select

from rhiz.state.base import Group, GroupStatus, GroupMember, Reckoning, ReckoningTypes, User
from rhiz.utils.slugs import slugify, unique_slug


def get_group_by_slug(session, slug: str):
    return session.exec(select(Group).where(Group.slug == slug)).first()


def get_group_for_concept(session, concept_id: int):
    return session.exec(select(Group).where(Group.concept_id == concept_id)).first()


def create_group(session, name: str, founding_question: str, created_by: int):
    """Create a group from scratch.

    A group has its own founding question (stored as a concept scoped to the
    group via group_id) and serves as a container for user-submitted concepts.
    """

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

    # Capture PostHog event for group creation.
    try:
        from rhiz.rhiz import posthog

        if posthog:
            posthog.capture(
                "group_created",
                distinct_id=f"group-{group.id}",
                properties={
                    "created_by": created_by,
                    "name_length": len(name),
                },
            )
    except Exception:
        pass  # PostHog failures should not block group creation.

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
    existing = get_membership(session, user_id, group_id)
    if existing:
        return existing
    member = GroupMember(user_id=user_id, group_id=group_id)
    session.add(member)
    session.commit()
    session.refresh(member)
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
