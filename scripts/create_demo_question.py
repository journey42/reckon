"""Add a permanent Q&A for /demo and make it the one that page shows.

The same thing the facilitator dashboard does — a room with "no timer" as its
length, then the /demo dropdown — as one command, so the first question can be put
in place on a fresh environment without clicking through the UI.

Idempotent: an existing question with the same wording is reused rather than
duplicated, and it is only made the active one when /demo has nothing else to
show — unless ``--activate`` says otherwise.

    DB_URL=postgresql://... python scripts/create_demo_question.py "Your question?"
    DB_URL=postgresql://... python scripts/create_demo_question.py --activate "Another?"
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import reflex as rx  # noqa: E402
from sqlmodel import select  # noqa: E402

from rhiz.state.base import Group, User  # noqa: E402
from rhiz.utils import demo  # noqa: E402

DEFAULT_QUESTION = (
    "What is something you think most people in your city agree on "
    "but nobody says out loud?"
)


def owner(session) -> User:
    """The account that owns demo questions: an admin, oldest first.

    Demo questions belong to an organiser rather than to a session, so the
    dashboard that manages them has a real person to show them to.
    """
    user = session.exec(
        select(User).where(User.role >= 2).order_by(User.id).limit(1)
    ).first()
    if user is None:
        raise SystemExit(
            "No admin account exists to own the question. Create one first, or "
            "add the question from the /live dashboard while signed in."
        )
    return user


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    activate = "--activate" in sys.argv
    question = (args[0] if args else DEFAULT_QUESTION).strip()

    with rx.session() as session:
        existing = session.exec(
            select(Group).where(Group.founding_question == question)
        ).first()
        if existing is not None and demo.is_demo_question(existing):
            room = existing
            print(f"Already exists: /demo/{room.slug}")
        elif existing is not None:
            raise SystemExit(
                f"A question with that wording already exists as a timed room "
                f"(/room/{existing.slug}). Ask it with different wording, or "
                "extend that room instead."
            )
        else:
            room = demo.create_demo_question(session, question, owner(session).id)
            print(f"Created: /demo/{room.slug}")

        current = demo.read_active_slug(session)
        if activate or not current or current == room.slug:
            demo.write_active_slug(session, room.slug)
            print(f"/demo now asks: {question}")
        else:
            print(
                f"/demo still asks another question (slug {current}); "
                "re-run with --activate to switch it."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
