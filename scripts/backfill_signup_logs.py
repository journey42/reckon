#!/usr/bin/env python
"""Attribute historical "signed up" log rows to their user.

Bug: signup() built its Log row with user_id=new_user.id *before* the commit,
so the id was still None. Every signup log in the database was therefore
written with a NULL user, and the signup history could not be attributed to
anyone. Fixed in rhiz/state/auth.py; this repairs the rows already written.

Matching is safe because both rows are created in the same request: the log's
created_at is generated microseconds after the user's, so the log is always at
or slightly after the account. Each log is matched to the unique user whose
created_at falls in [log.created_at - 1s, log.created_at]. Verified 1:1 in both
directions before this script existed; the script re-checks that and refuses to
guess if it ever stops holding.

Usage:
    python scripts/backfill_signup_logs.py           # dry run
    python scripts/backfill_signup_logs.py --apply   # write
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("DB_URL", "sqlite:///reflex.db")

from sqlalchemy import text  # noqa: E402
import reflex as rx  # noqa: E402

MATCH_SQL = text(
    """
    WITH orphans AS (
        SELECT id, created_at FROM log
        WHERE type = 'user' AND content = 'signed up' AND user_id IS NULL
    ),
    cand AS (
        SELECT o.id AS log_id, u.id AS user_id
        FROM orphans o
        JOIN "user" u
          ON o.created_at >= u.created_at
         AND EXTRACT(EPOCH FROM (o.created_at - u.created_at)) <= 1.0
    ),
    per_log AS (
        SELECT log_id, count(*) AS n, min(user_id) AS user_id FROM cand GROUP BY log_id
    ),
    per_user AS (
        SELECT user_id, count(*) AS n FROM cand GROUP BY user_id
    )
    SELECT
        (SELECT count(*) FROM orphans)                                        AS orphans,
        (SELECT count(*) FROM per_log)                                        AS matched,
        (SELECT count(*) FROM per_log WHERE n > 1)                            AS ambiguous_logs,
        (SELECT count(*) FROM per_user WHERE n > 1)                           AS doubled_users
    """
)

UPDATE_SQL = text(
    """
    WITH cand AS (
        SELECT l.id AS log_id, u.id AS user_id
        FROM log l
        JOIN "user" u
          ON l.created_at >= u.created_at
         AND EXTRACT(EPOCH FROM (l.created_at - u.created_at)) <= 1.0
        WHERE l.type = 'user' AND l.content = 'signed up' AND l.user_id IS NULL
    ),
    safe AS (
        SELECT log_id, min(user_id) AS user_id FROM cand
        GROUP BY log_id
        HAVING count(*) = 1
           AND min(user_id) IN (
               SELECT user_id FROM cand c2 GROUP BY user_id HAVING count(*) = 1
           )
    )
    UPDATE log SET user_id = safe.user_id
    FROM safe WHERE log.id = safe.log_id
    """
)


def main() -> int:
    apply = "--apply" in sys.argv
    with rx.session() as session:
        orphans, matched, ambiguous, doubled = session.execute(MATCH_SQL).all()[0]
        print(f"unattributed signup logs : {orphans}")
        print(f"matched to one user      : {matched}")
        print(f"ambiguous (2+ candidates): {ambiguous}")
        print(f"users claimed twice      : {doubled}")

        if orphans == 0:
            print("Nothing to do.")
            return 0
        if ambiguous or doubled or matched != orphans:
            print(
                "\nRefusing to guess: the 1:1 timestamp match no longer holds. "
                "Inspect the candidates before writing."
            )
            return 1
        if not apply:
            print(f"\nDry run. Re-run with --apply to attribute {matched} rows.")
            return 0

        result = session.execute(UPDATE_SQL)
        session.commit()
        print(f"\nUpdated {result.rowcount} log rows.")
        remaining = session.execute(
            text(
                "SELECT count(*) FROM log WHERE type='user' "
                "AND content='signed up' AND user_id IS NULL"
            )
        ).all()[0][0]
        print(f"Still unattributed: {remaining}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
