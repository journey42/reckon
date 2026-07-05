"""Apply pending DB migrations directly via SQL (no Alembic dependency).

Since the base migration files (5c4374b3a58f_, b2f1a9c4d7e3) are not tracked
in git and don't exist in the container, Alembic's ScriptDirectory can't
resolve the revision chain. This script applies the needed schema changes
directly via SQL, bypassing Alembic entirely.

Usage:
    python scripts/db_migrate.py
"""

import os
import sys

from sqlalchemy import create_engine, text, inspect


def get_db_url() -> str:
    """Get database URL from environment, falling back to alembic.ini."""
    url = os.getenv("DB_URL")
    if url:
        return url
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read("alembic.ini")
    return cfg.get("alembic", "sqlalchemy.url")


def main():
    db_url = get_db_url()
    print(f"[migrate] Connecting to database...", flush=True)

    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"[migrate] Existing tables: {', '.join(sorted(tables))}", flush=True)

    with engine.connect() as conn:
        conn.execute(text("BEGIN"))

        # 1. Rename debate → group table + columns
        if "debate" in tables:
            print(f"[migrate] Renaming debate → group table...", flush=True)
            conn.execute(text("ALTER TABLE debate RENAME COLUMN title TO name"))
            conn.execute(text("ALTER TABLE debate RENAME COLUMN intro TO founding_question"))
            conn.execute(text('ALTER TABLE debate RENAME TO "group"'))
            print(f"[migrate] Table rename complete.", flush=True)
        elif "group" in tables:
            print(f"[migrate] Debate table already renamed to group.", flush=True)
        else:
            print(f"[migrate] Neither debate nor group table found.", flush=True)

        # 2. Add/rename can_create_groups column on user table
        user_cols = [c["name"].lower() for c in inspector.get_columns("user")]
        if "can_create_groups" in user_cols:
            print(f"[migrate] can_create_groups column already exists.", flush=True)
        elif "can_create_debates" in user_cols:
            print(f"[migrate] Renaming can_create_debates → can_create_groups...", flush=True)
            conn.execute(
                text('ALTER TABLE "user" RENAME COLUMN can_create_debates TO can_create_groups')
            )
        else:
            print(f"[migrate] Adding can_create_groups column...", flush=True)
            conn.execute(
                text('ALTER TABLE "user" ADD COLUMN can_create_groups BOOLEAN DEFAULT FALSE')
            )

        # 3. Ensure alembic_version table exists for future Alembic-based migrations
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))"
            )
        )
        # Stamp at 1a879f6b06c3 (our rename migration) so future Alembic migrations
        # can build on top of it.
        existing = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        if not existing:
            conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('1a879f6b06c3')")
            )
            print(f"[migrate] Stamped alembic_version at 1a879f6b06c3.", flush=True)
        else:
            print(f"[migrate] alembic_version already stamped at {existing[0]}.", flush=True)

        conn.execute(text("COMMIT"))

    engine.dispose()
    print(f"[migrate] Migration complete.", flush=True)


if __name__ == "__main__":
    main()