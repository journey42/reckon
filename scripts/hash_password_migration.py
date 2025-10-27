"""One-time password hashing migration script."""

from __future__ import annotations

import sys
from datetime import datetime
import reflex as rx
from sqlalchemy.orm import Session
from sqlmodel import select

from reckon.state.base import User
from reckon.utils.security import hash_password, is_hashed


def migrate_passwords(session: Session, *, dry_run: bool = False) -> int:
    """Hash any legacy plaintext passwords.

    Args:
        session: Active database session.
        dry_run: When True, no changes are written to the database.

    Returns:
        The number of user records that were migrated.
    """
    migrated = 0
    users = session.exec(select(User)).all()

    for user in users:
        password = user.password or ""
        if not password:
            continue
        if is_hashed(password):
            continue

        migrated += 1
        print(f"Hashing password for user '{user.username}' (id={user.id})")

        if dry_run:
            continue

        user.password = hash_password(password)
        user.updated_at = datetime.utcnow()
        session.add(user)

    if dry_run:
        session.rollback()
    else:
        session.commit()

    return migrated


def main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv

    with rx.session() as session:
        count = migrate_passwords(session, dry_run=dry_run)

    suffix = " (dry run)" if dry_run else ""
    print(f"Migrated {count} user password(s){suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
