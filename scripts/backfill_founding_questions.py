"""Fill in group founding questions that live only on the founding concept.

A group keeps its question in two places: the ``founding_question`` column and
the founding concept (``group.concept_id`` → ``reckoning.content``). Rows written
before that column existed, or by a path that populated only one side, show up as
a group page with an empty "Your group has asked:" — the header reads the column.
The page now falls back to the concept (``rhiz.utils.groups.founding_text``), and
this script closes the gap in the data itself so the column, the concept, the
Discord/X link preview and any exported artifact all say the same thing.

Dry run by default: it prints what it would change and writes nothing until
``--apply``.

    DB_URL=postgresql://... python scripts/backfill_founding_questions.py
    DB_URL=postgresql://... python scripts/backfill_founding_questions.py --apply
"""

import os
import sys

from sqlalchemy import create_engine, text

SQL_FIND = text(
    """
    select g.id,
           g.slug,
           g.name,
           coalesce(g.founding_question, '') as question,
           coalesce(r.content, '') as concept_content
      from "group" g
      left join reckoning r on r.id = g.concept_id
     where coalesce(g.founding_question, '') = ''
     order by g.id
    """
)

SQL_SET = text('update "group" set founding_question = :question where id = :id')


def get_db_url() -> str:
    url = os.getenv("DB_URL")
    if url:
        return url
    import configparser

    ini = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    parser = configparser.ConfigParser()
    parser.read(ini)
    url = parser.get("alembic", "sqlalchemy.url", fallback="")
    if not url:
        raise SystemExit("Set DB_URL or fill in alembic.ini")
    return url


def main() -> int:
    apply = "--apply" in sys.argv
    engine = create_engine(get_db_url())

    with engine.begin() as conn:
        rows = conn.execute(SQL_FIND).mappings().all()

    repairable = [r for r in rows if r["concept_content"].strip()]
    hopeless = [r for r in rows if not r["concept_content"].strip()]

    print(f"{len(rows)} group(s) with no founding question on the row.")
    print(f"{len(repairable)} can be filled from their founding concept.")
    print(f"{len(hopeless)} have nothing in either place and need a person.\n")

    for row in repairable:
        preview = row["concept_content"].strip().replace("\n", " ")[:72]
        print(f"  #{row['id']:<6} {row['slug'][:28]:<28} -> {preview}")

    if hopeless:
        print("\nCannot be repaired from data — the question is gone:")
        for row in hopeless:
            print(f"  #{row['id']:<6} {row['slug'][:28]:<28} {row['name'][:40]}")

    if not repairable:
        print("\nNothing to do.")
        return 0

    if not apply:
        print(f"\nDry run. Re-run with --apply to write {len(repairable)} row(s).")
        return 0

    with engine.begin() as conn:
        for row in repairable:
            conn.execute(
                SQL_SET,
                {"id": row["id"], "question": row["concept_content"].strip()},
            )
    print(f"\nUpdated {len(repairable)} group(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
