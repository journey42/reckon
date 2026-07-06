"""Data-access helpers for group pages."""

from datetime import datetime, timezone

from sqlmodel import select

from rhiz.state.base import Group, GroupStatus, Reckoning, ReckoningTypes
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
    """Delete a group and all its concepts/comments.

    If owner_id is given, only delete when that user owns it. Admins pass
    owner_id=None to delete any group.
    """
    group = session.exec(select(Group).where(Group.id == group_id)).first()
    if group is None:
        return
    if owner_id is not None and group.created_by != owner_id:
        return
    # Delete all group-scoped reckonings (concepts + their comment trees)
    from sqlalchemy import delete as sa_delete

    session.exec(sa_delete(Reckoning).where(Reckoning.group_id == group_id))
    session.delete(group)
    session.commit()
