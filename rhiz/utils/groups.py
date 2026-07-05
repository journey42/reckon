"""Data-access helpers for group pages."""

from datetime import datetime, timezone

from sqlmodel import select

from rhiz.state.base import Group, GroupStatus, Reckoning, ReckoningTypes
from rhiz.utils.slugs import slugify, unique_slug


def get_group_by_slug(session, slug: str):
    return session.exec(select(Group).where(Group.slug == slug)).first()


def get_group_for_concept(session, concept_id: int):
    return session.exec(
        select(Group).where(Group.concept_id == concept_id)
    ).first()


def create_group(session, name: str, founding_question: str, created_by: int):
    """Create a group from scratch.

    A group is a standalone question — distinct from the old debate flow which
    wrapped an existing concept. This creates a new concept (type=concept) with
    the founding question as content, then links a Group record to it.
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
        created_by=created_by,
    )
    session.add(group)
    session.commit()
    session.refresh(group)

    # Capture PostHog event for group creation.
    try:
        from rhiz.rhiz import posthog
        if posthog:
            posthog.capture("group_created", distinct_id=f"group-{group.id}", properties={
                "created_by": created_by,
                "name_length": len(name),
            })
    except Exception:
        pass  # PostHog failures should not block group creation.

    return group


def set_group_status(session, group_id: int, status: str) -> None:
    group = session.exec(select(Group).where(Group.id == group_id)).first()
    if group is not None:
        group.status = status
        session.commit()


def delete_group(session, group_id: int, owner_id: int | None = None) -> None:
    """Delete a group. If owner_id is given, only delete it when that user
    owns it (used by the per-user view); admins pass owner_id=None to delete
    any group. The referenced concept is left untouched."""
    group = session.exec(select(Group).where(Group.id == group_id)).first()
    if group is None:
        return
    if owner_id is not None and group.created_by != owner_id:
        return
    session.delete(group)
    session.commit()
