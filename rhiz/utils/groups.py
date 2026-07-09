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
    """Delete a group and all its concepts, comments, and votes.

    Handles the circular FK: group.concept_id → reckoning.id (NOT NULL) AND
    reckoning.group_id → group.id (nullable).  We null out group_id on all
    affected reckonings first, then delete the group, then delete the
    reckonings.
    """
    group = session.exec(select(Group).where(Group.id == group_id)).first()
    if group is None:
        return
    if owner_id is not None and group.created_by != owner_id:
        return
    from sqlalchemy import text

    concept_id = group.concept_id

    # Step 1: Null out reckoning.group_id for all group-scoped reckonings
    # so the group row can be deleted (breaks reckoning→group FK).
    session.execute(
        text("UPDATE reckoning SET group_id = NULL WHERE group_id = :gid"),
        {"gid": group_id},
    )
    session.commit()

    # Step 2: Delete the group row (concept_id FK still references the
    # founding concept, but group→reckoning direction is fine).
    session.delete(group)
    session.commit()

    # Step 3: Now delete all the reckonings — the founding concept and
    # all its descendants (comments, votes, sub-concepts).
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

    session.expire_all()
