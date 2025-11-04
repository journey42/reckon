"""Utility script to regenerate embeddings with the FastEmbed model."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import reflex as rx
from sqlmodel import select
from sqlalchemy.sql import text

from rhiz.state.base import Reckoning, ReckoningTypes
from rhiz.utils.db import insert_text_with_embedding
from rhiz.utils.parsing import remove_html_tags


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_identifier(name: str) -> str:
    """Return a safely quoted identifier for SQL usage."""

    if not IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe identifier: {name}")
    return f'"{name}"'


def create_embeddings_backup(
    table_name: str | None = None, overwrite: bool = False
) -> str:
    """Copy the embeddings table into a timestamped backup."""

    suffix = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    name = table_name or f"embeddings_backup_{suffix}"

    quoted_name = _quote_identifier(name)

    with rx.session() as session:
        embeddings_exists = session.execute(
            text("SELECT to_regclass('embeddings')")
        ).scalar()
        if not embeddings_exists:
            raise RuntimeError("embeddings table does not exist; nothing to back up.")

        existing = session.execute(
            text("SELECT to_regclass(:name)"), {"name": name}
        ).scalar()

        if existing:
            if not overwrite:
                raise RuntimeError(
                    f"Backup table '{name}' already exists. Use --overwrite-backup to replace it."
                )
            session.execute(text(f"DROP TABLE {quoted_name}"))

        session.execute(
            text(f"CREATE TABLE {quoted_name} (LIKE embeddings INCLUDING ALL)")
        )
        session.execute(text(f"INSERT INTO {quoted_name} SELECT * FROM embeddings"))
        session.commit()

    return name


def _batched_reckonings(batch_size: int, start_after: int | None = None):
    """Yield concept reckonings in ascending ID order."""

    last_id = start_after or 0
    while True:
        with rx.session() as session:
            query = (
                select(Reckoning.id, Reckoning.content)
                .where(Reckoning.type == ReckoningTypes.concept)
                .order_by(Reckoning.id)
                .limit(batch_size)
            )
            if last_id:
                query = query.where(Reckoning.id > last_id)

            rows = session.exec(query).all()

        if not rows:
            return

        for rid, content in rows:
            yield rid, content
            last_id = rid


def regenerate_embeddings(batch_size: int = 100, dry_run: bool = False) -> int:
    """Regenerate embeddings for all concept reckonings."""

    if batch_size <= 0:
        raise ValueError("batch_size must be positive.")

    processed = 0
    for rid, content in _batched_reckonings(batch_size=batch_size):
        cleaned = remove_html_tags(content or "")
        if dry_run:
            print(f"[DRY-RUN] Would update embedding for reckoning {rid}")
        else:
            insert_text_with_embedding(cleaned, rid)
        processed += 1
        if processed % batch_size == 0:
            print(f"Processed {processed} concepts (last id {rid})", flush=True)

    return processed


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate embeddings for existing concept reckonings."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of concepts to process per batch.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Walk through the records without writing embeddings.",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Do not create a backup copy of the embeddings table before writing.",
    )
    parser.add_argument(
        "--backup-table-name",
        type=str,
        help="Custom name for the backup table (defaults to embeddings_backup_<timestamp>).",
    )
    parser.add_argument(
        "--overwrite-backup",
        action="store_true",
        help="Drop any existing backup table with the same name before creating a new one.",
    )
    args = parser.parse_args()

    backup_table = None
    if not args.dry_run and not args.skip_backup:
        backup_table = create_embeddings_backup(
            table_name=args.backup_table_name, overwrite=args.overwrite_backup
        )
        print(f"Created backup table '{backup_table}'.")

    total = regenerate_embeddings(batch_size=args.batch_size, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    backup_note = f" Backup table: {backup_table}." if backup_table else ""
    print(f"Completed embedding regeneration for {total} concepts{suffix}.{backup_note}")


if __name__ == "__main__":
    main()
