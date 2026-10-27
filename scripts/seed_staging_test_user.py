#!/usr/bin/env python3
"""Create the two accounts the staging regression pass signs in with.

Staging is a restore of production, so it holds real people's rows and none of
them are ours to sign in as. This makes exactly two throwaway accounts — one
admin, one ordinary — enabled and verified so the pass can exercise both sides
of every permission check.

    DB_URL=<staging dsn> python scripts/seed_staging_test_user.py

Credentials come from the environment; nothing is printed:

    RHIZ_REG_ADMIN_PASSWORD   (required)
    RHIZ_REG_USER_PASSWORD    (required)

The DB host is checked first and the script refuses to run against anything
that is not staging or a local database, because "point the staging seed script
at production" is the one mistake that cannot be undone here.
"""

from __future__ import annotations

import datetime
import os
import re
import sys
from urllib.parse import urlparse

import sqlalchemy as sa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import reflex as rx

from rhiz.state.base import User
from rhiz.utils.security import hash_password

PROD_HOST_PATTERNS = (
    re.compile(r"^reckon-db\."),  # reckon-db.postgres.database.azure.com
    re.compile(r"rhiz\.ai$"),
)

ADMIN_USER = os.environ.get("RHIZ_REG_ADMIN_USER", "regtest_admin")
PLAIN_USER = os.environ.get("RHIZ_REG_USER_USER", "regtest_user")

# Two groups the regression pass opens, so it always has something to assert
# about regardless of what the restore happened to contain: one that keeps its
# wording the normal way, and one shaped like the rows written before the
# founding_question column existed — wording only on the founding concept.
GROUP_SPECS = (
    ("Regression pass group", "What should the regression pass ask this group?", False),
    (
        "Regression pass group legacy wording",
        "What does a group with wording only on its concept ask?",
        True,
    ),
)

# Two live questions convened by the admin account, so the Extend control has
# something to be checked against on either side of the deadline rule. They are
# owned by that account because the facilitator controls are per-question, and
# the restore's own questions are other people's.
ROOM_SPECS = (
    ("Regression pass live question with a timer", False),
    ("Regression pass live question with no timer", True),
)


def _db_host(db_url: str) -> str:
    """The database host, however awkward the DSN is.

    urlparse is not enough, and neither is the obvious regex: the real
    credentials contain `@` and `?`, so "strip the query string, then split at
    the last @" cuts the host off the middle of the password and returns
    garbage that *looks* like a local name — which for a guard is the worst
    failure it can have. libpq resolves the same ambiguity by treating the last
    `@` as the separator, so that is what this does, and only then does it drop
    the path, query and port.
    """
    tail = db_url
    if "@" in tail:
        tail = tail.rsplit("@", 1)[1]
    tail = re.sub(r"^[a-z+]+://", "", tail, flags=re.I)
    host = re.split(r"[/?#]", tail, 1)[0]
    host = host.rsplit(":", 1)[0] if ":" in host else host
    return host.strip("[]").lower()


def _guard(db_url: str) -> str:
    host = _db_host(db_url)
    if not host:
        sys.exit("DB_URL has no host — refusing to guess where it points.")
    if any(p.search(host) for p in PROD_HOST_PATTERNS):
        sys.exit(
            f"DB_URL points at {host}, which is production. This script writes "
            "rows; run it against the staging restore instead."
        )
    if not (host.startswith("localhost") or host.startswith("127.0.0.1") or "staging" in host):
        sys.exit(
            f"DB_URL points at {host} — that is neither staging nor local, so "
            "this script will not touch it."
        )
    return host


def main() -> int:
    db_url = os.environ.get("DB_URL", "")
    if not db_url:
        sys.exit("Set DB_URL to the staging database's DSN.")
    host = _guard(db_url)

    admin_pw = os.environ.get("RHIZ_REG_ADMIN_PASSWORD", "")
    user_pw = os.environ.get("RHIZ_REG_USER_PASSWORD", "")
    if not admin_pw or not user_pw:
        sys.exit("Set RHIZ_REG_ADMIN_PASSWORD and RHIZ_REG_USER_PASSWORD.")
    if len(admin_pw) < 10 or len(user_pw) < 10:
        sys.exit("Passwords must be at least 10 characters.")

    engine = sa.create_engine(db_url)
    now = datetime.datetime.now(datetime.timezone.utc)

    with engine.begin() as conn:
        for username, password, role in (
            (ADMIN_USER, admin_pw, 2),  # UserTypes.admin
            (PLAIN_USER, user_pw, 0),  # UserTypes.regular
        ):
            existing = conn.execute(
                sa.text('SELECT id FROM "user" WHERE username = :u'), {"u": username}
            ).first()
            values = {
                "u": username,
                "e": f"{username}@staging.rhiz.test",
                "p": hash_password(password),
                "r": role,
                "at": now,
            }
            if existing is None:
                conn.execute(
                    sa.text(
                        'INSERT INTO "user" (username, password, email, enabled, role,'
                        " can_create_groups, created_at)"
                        " VALUES (:u, :p, :e, true, :r, true, :at)"
                    ),
                    values,
                )
            else:
                # A restore may already contain the name; reset it rather than
                # fail, so the pass is re-runnable after every re-restore.
                conn.execute(
                    sa.text(
                        'UPDATE "user" SET password = :p, email = :e, enabled = true,'
                        " role = :r, can_create_groups = true,"
                        " verification_token = null, verification_expires_at = null"
                        ' WHERE username = :u'
                    ),
                    values,
                )
    engine.dispose()

    slugs = _seed_groups()
    rooms = _seed_rooms()

    print(f"seeded 2 accounts on {host}: {ADMIN_USER} (admin), {PLAIN_USER} (regular)")
    for slug, legacy in slugs:
        print(f"  group /group/{slug}" + ("  (wording on the concept only)" if legacy else ""))
    for slug, permanent in rooms:
        print(f"  room  /room/{slug}" + ("  (no timer)" if permanent else "  (timed)"))
    return 0


def _seed_rooms() -> list[tuple[str, bool]]:
    """The two live questions the pass opens, convened by the admin account."""
    import reflex as rx
    from sqlmodel import select

    from rhiz.state.base import Group, GroupStatus
    from rhiz.utils.rooms import create_room

    out: list[tuple[str, bool]] = []
    with rx.session() as session:
        admin = session.exec(select(User).where(User.username == ADMIN_USER)).first()
        for question, permanent in ROOM_SPECS:
            room = session.exec(
                select(Group).where(Group.founding_question == question)
            ).first()
            # 120 minutes, not the default: a room that expires halfway through a
            # test session would make the pass flaky.
            lifespan = 120
            if room is None:
                room = create_room(
                    session,
                    question=question,
                    created_by=admin.id,
                    duration_minutes=lifespan,
                    permanent=permanent,
                )
            elif not permanent and room.close_at is not None:
                # Re-running this script is how you revive the fixtures, so it has
                # to actually revive them: a timed room from a previous session is
                # closed by now, and the pass's Extend check needs an open one.
                # Leaving it expired made "re-run the seed" advice that did
                # nothing, while the check passed on the permanent room alone.
                now = datetime.datetime.now(datetime.timezone.utc)
                room.close_at = now + datetime.timedelta(minutes=lifespan)
                room.status = GroupStatus.open
                session.add(room)
                session.commit()
                session.refresh(room)
            out.append((room.slug, permanent))
    return out


def _seed_groups() -> list[tuple[str, bool]]:
    """Make the two groups the pass reads, or refresh them if a restore already
    has them. Goes through the app's own ``create_group`` so the rows are shaped
    exactly like real ones, including the founding concept."""
    import reflex as rx
    from sqlmodel import select

    from rhiz.state.base import Group
    from rhiz.utils.groups import create_group
    out: list[tuple[str, bool]] = []
    with rx.session() as session:
        admin = session.exec(select(User).where(User.username == ADMIN_USER)).first()
        if admin is None:  # pragma: no cover - main() creates it first
            raise SystemExit(f"{ADMIN_USER} was not created; cannot seed groups.")
        for name, question, legacy in GROUP_SPECS:
            group = session.exec(select(Group).where(Group.name == name)).first()
            if group is None:
                group = create_group(
                    session, name=name, founding_question=question, created_by=admin.id
                )
            group.is_public = True
            # The legacy row keeps its wording on the concept and nothing in the
            # column, which is the exact shape that made group pages render an
            # empty question.
            group.founding_question = "" if legacy else question
            session.add(group)
            session.commit()
            out.append((group.slug, legacy))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
