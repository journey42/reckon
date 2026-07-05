"""rename debate table to group and update columns

Rename `debate` → `group`, `title` → `name`, `intro` → `founding_question`.
The slug index keeps the same column name so the rename is safe against any
existing row data.
Conditionally rename `can_create_debates` → `can_create_groups` on user table
(was added manually in production, may not exist in all environments).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "1a879f6b06c3"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE debate RENAME COLUMN title TO name")
    op.execute("ALTER TABLE debate RENAME COLUMN intro TO founding_question")
    op.execute("ALTER TABLE debate RENAME TO \"group\"")
    # Rename can_create_debates → can_create_groups if the old column exists
    conn = op.get_bind()
    col_exists = conn.execute(
        """SELECT column_name FROM information_schema.columns
               WHERE table_name='user' AND column_name='can_create_debates'"""
    ).fetchone()
    if col_exists:
        op.execute(
            "ALTER TABLE \"user\" RENAME COLUMN can_create_debates TO can_create_groups"
        )


def downgrade() -> None:
    conn = op.get_bind()
    col_exists = conn.execute(
        """SELECT column_name FROM information_schema.columns
               WHERE table_name='user' AND column_name='can_create_groups'"""
    ).fetchone()
    if col_exists:
        op.execute(
            "ALTER TABLE \"user\" RENAME COLUMN can_create_groups TO can_create_debates"
        )
    op.execute("ALTER TABLE \"group\" RENAME TO debate")
    op.execute("ALTER TABLE debate RENAME COLUMN name TO title")
    op.execute("ALTER TABLE debate RENAME COLUMN founding_question TO intro")
