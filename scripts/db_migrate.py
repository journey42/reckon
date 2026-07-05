"""Bootstrap and run Alembic migrations.

Handles the case where the alembic_version table doesn't exist yet
(common on first deploy or when reflex db init was never run).

Usage:
    python scripts/db_migrate.py
"""

import os
import sys

# Ensure we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text, inspect


def get_db_url() -> str:
    """Get database URL from environment, falling back to alembic.ini."""
    url = os.getenv("DB_URL")
    if url:
        return url
    # Fallback: read from alembic.ini
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read("alembic.ini")
    return cfg.get("alembic", "sqlalchemy.url")


def get_current_head() -> str:
    """Get the current Alembic head revision."""
    from alembic.script import ScriptDirectory
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    return scripts.get_current_head()


def main():
    db_url = get_db_url()
    print(f"[migrate] Connecting to database...", flush=True)

    engine = create_engine(db_url)
    inspector = inspect(engine)

    tables = inspector.get_table_names()
    print(f"[migrate] Existing tables: {', '.join(sorted(tables))}", flush=True)

    has_version_table = "alembic_version" in tables

    if not has_version_table:
        # Determine which revision to stamp by looking at applied migrations.
        # If the debate table exists, the old migrations were applied.
        # Otherwise, stamp at the very start.

        # We check for the oldest migration's tables to determine starting point
        has_debate_table = "debate" in tables
        has_user_table = "user" in tables

        if has_debate_table:
            # The debate table migration (c3d4e5f6a7b8) was applied.
            # The user-verification migration (d4e5f6a7b8c9) may also be applied.
            has_verification = False
            if has_user_table:
                cols = [c["name"] for c in inspector.get_columns("user")]
                has_verification = "verification_token" in cols

            stamp_revision = "d4e5f6a7b8c9" if has_verification else "c3d4e5f6a7b8"
            print(f"[migrate] alembic_version table missing. Stamping at {stamp_revision}...", flush=True)

            with engine.connect() as conn:
                conn.execute(text(f"CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))"))
                conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{stamp_revision}')"))
                conn.commit()
            print(f"[migrate] Stamped at {stamp_revision}.", flush=True)
        else:
            print(f"[migrate] No existing tables found. Running full migration from scratch...", flush=True)
    else:
        # Read current revision
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            current = row[0] if row else None
            print(f"[migrate] alembic_version table exists, current revision: {current}", flush=True)

    engine.dispose()

    # Now run alembic upgrade head
    print(f"[migrate] Running: alembic upgrade head...", flush=True)
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print(f"[migrate] Migration complete.", flush=True)


if __name__ == "__main__":
    main()