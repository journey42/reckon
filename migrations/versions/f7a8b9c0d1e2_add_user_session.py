"""add usersession table for cookie-backed persistent logins

Keeps users logged in across backend restarts, state-manager evictions and new
client tokens - the conditions that previously appeared as being "kicked out"
mid-session.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-24 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usersession",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_used_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "revoked", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
    )
    op.create_index(
        "ix_usersession_token_hash", "usersession", ["token_hash"], unique=True
    )
    op.create_index("ix_usersession_user_id", "usersession", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_usersession_user_id", table_name="usersession")
    op.drop_index("ix_usersession_token_hash", table_name="usersession")
    op.drop_table("usersession")
