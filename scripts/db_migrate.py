"""Apply pending DB migrations directly via Alembic.

This script applies migrations using Alembic's Python API, configuring
the engine URL from the DB_URL environment variable so it works with
Azure Container Apps' secret-reference URLs.

Usage:
    python scripts/db_migrate.py
"""

import os
import sys

from sqlalchemy import create_engine, text, inspect

from alembic.config import Config
from alembic import command


def get_db_url() -> str:
    """Get database URL from environment, falling back to alembic.ini."""
    url = os.getenv("DB_URL")
    if url:
        return url
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read("alembic.ini")
    return cfg.get("alembic", "sqlalchemy.url")


def known_revisions():
    """Return the set of revision IDs that exist as migration files."""
    import re
    revisions = set()
    versions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations", "versions")
    if not os.path.isdir(versions_dir):
        return revisions
    for fn in os.listdir(versions_dir):
        if not fn.endswith(".py"):
            continue
        fp = os.path.join(versions_dir, fn)
        try:
            with open(fp) as f:
                content = f.read()
        except Exception:
            continue
        m = re.search(r'^revision:\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if m:
            revisions.add(m.group(1))
    return revisions


def stamp_at(alembic_cfg: Config, revision: str):
    """Stamp the alembic_version table to the given revision."""
    print(f"[migrate] Stamping alembic_version at {revision}...", flush=True)
    command.stamp(alembic_cfg, revision)


def main():
    db_url = get_db_url()
    print(f"[migrate] Connecting to database...", flush=True)

    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"[migrate] Existing tables: {', '.join(sorted(tables))}", flush=True)

    # Build Alembic config with correct DB URL
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "migrations")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    has_version_table = "alembic_version" in tables
    known = known_revisions()
    print(f"[migrate] Known revisions: {', '.join(sorted(known))}", flush=True)

    if has_version_table:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            current = row[0] if row else None
            print(f"[migrate] alembic_version exists, revision: {current}", flush=True)

        if current and current not in known:
            print(f"[migrate] Unknown revision {current} — overwriting...", flush=True)
            has_debate = "debate" in tables
            if has_debate:
                # Figure out correct stamp
                cols = [c["name"].lower() for c in inspector.get_columns("user")]
                stamp = "d4e5f6a7b8c9" if "verification_token" in cols else "c3d4e5f6a7b8"
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM alembic_version"))
                    conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{stamp}')"))
                    conn.commit()
                print(f"[migrate] Overwrote with correct revision: {stamp}", flush=True)
            else:
                with engine.connect() as conn:
                    conn.execute(text("DELETE FROM alembic_version"))
                    conn.commit()
                print(f"[migrate] No migration tables — cleared alembic_version", flush=True)
    else:
        has_debate = "debate" in tables
        if has_debate:
            cols = [c["name"].lower() for c in inspector.get_columns("user")]
            stamp = "d4e5f6a7b8c9" if "verification_token" in cols else "c3d4e5f6a7b8"
            print(f"[migrate] alembic_version missing. Stamping at {stamp}...", flush=True)
            with engine.connect() as conn:
                conn.execute(
                    text("CREATE TABLE IF NOT EXISTS alembic_version "
                         "(version_num VARCHAR(32) NOT NULL, PRIMARY KEY (version_num))")
                )
                conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{stamp}')"))
                conn.commit()
            print(f"[migrate] Stamped at {stamp}.", flush=True)
        else:
            print(f"[migrate] No existing tables. Running fresh migration...", flush=True)

    engine.dispose()

    # Run migrations
    print(f"[migrate] Running: alembic upgrade head...", flush=True)
    try:
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        print(f"[migrate] ERROR: {e}", flush=True)
        sys.exit(1)

    print(f"[migrate] Migration complete.", flush=True)


if __name__ == "__main__":
    main()