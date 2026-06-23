"""Data-access helpers for debate pages."""

from sqlmodel import select

from rhiz.state.base import Debate, DebateStatus
from rhiz.utils.slugs import slugify, unique_slug


def get_debate_by_slug(session, slug: str):
    return session.exec(select(Debate).where(Debate.slug == slug)).first()


def get_debate_for_concept(session, concept_id: int):
    return session.exec(
        select(Debate).where(Debate.concept_id == concept_id)
    ).first()


def create_debate(session, concept_id: int, title: str, intro: str, created_by: int):
    """Create a debate for a concept (1:1). Raises ValueError if one exists."""
    if get_debate_for_concept(session, concept_id) is not None:
        raise ValueError("concept already has a debate")

    def _taken(candidate: str) -> bool:
        return get_debate_by_slug(session, candidate) is not None

    slug = unique_slug(slugify(title), _taken)
    debate = Debate(
        slug=slug,
        concept_id=concept_id,
        title=title,
        intro=intro or "",
        status=DebateStatus.open,
        created_by=created_by,
    )
    session.add(debate)
    session.commit()
    session.refresh(debate)
    return debate


def set_debate_status(session, debate_id: int, status: str) -> None:
    debate = session.exec(select(Debate).where(Debate.id == debate_id)).first()
    if debate is not None:
        debate.status = status
        session.commit()


def delete_debate(session, debate_id: int, owner_id: int | None = None) -> None:
    """Delete a debate. If owner_id is given, only delete it when that user
    owns it (used by the per-user view); admins pass owner_id=None to delete
    any debate. The referenced concept is left untouched."""
    debate = session.exec(select(Debate).where(Debate.id == debate_id)).first()
    if debate is None:
        return
    if owner_id is not None and debate.created_by != owner_id:
        return
    session.delete(debate)
    session.commit()
