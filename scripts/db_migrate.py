"""Bootstrap and run Alembic migrations.

Handles the case where the alembic_version table doesn't exist yet
(common on first deploy or when reflex db init was never run).

Usage:
    python scripts/db_migrate.py
"""

import os
import subprocess
import sys

# Ensure we can import from project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

    has_version_table = "alembic_version" in tables

    if not has_version_table:
        has_debate_table = "debate" in tables
        has_user_table = "user" in tables

        if has_debate_table:
            has_verification = False
            if has_user_table:
                cols = [c["name"].lower() for c in inspector.get_columns("user")]
                has_verification = "verification_token" in cols

            stamp_revision = "d4e5f6a7b8c9" if has_verification else "c3d4e5f6a7b8"
            print(
                f"[migrate] alembic_version missing. Stamping at {stamp_revision}...",
                flush=True,
            )

            with engine.connect() as conn:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS alembic_version "
                        "(version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))"
                    )
                )
                conn.execute(
                    text(
                        f"INSERT INTO alembic_version (version_num) VALUES ('{stamp_revision}')"
                    )
                )
                conn.commit()
            print(f"[migrate] Stamped at {stamp_revision}.", flush=True)
        else:
            print(
                f"[migrate] No existing tables. Running full migration from scratch...",
                flush=True,
            )
    else:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            current = row[0] if row else None
            print(f"[migrate] alembic_version exists, revision: {current}", flush=True)

    engine.dispose()

    # Run alembic upgrade head via CLI (pass DB_URL so env.py can use it)
    print(f"[migrate] Running: alembic upgrade head...", flush=True)
    env = os.environ.copy()
    env["DB_URL"] = db_url
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout, flush=True)
    if result.stderr:
        print(result.stderr, flush=True, file=sys.stderr)
    if result.returncode != 0:
        print(f"[migrate] ERROR: alembic upgrade head failed (exit {result.returncode})", flush=True)
        sys.exit(result.returncode)

    print(f"[migrate] Migration complete.", flush=True)


if __name__ == "__main__":
    main()