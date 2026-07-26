"""add group_member table for explicit group membership tracking

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2025-07-12 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = ["1a879f6b06c3", "d4e5f6a7b8c9"]
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "groupmember",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["group.id"]),
        sa.UniqueConstraint("user_id", "group_id", name="uq_user_group"),
    )
    op.create_index(
        "ix_groupmember_user_id", "groupmember", ["user_id"]
    )
    op.create_index(
        "ix_groupmember_group_id", "groupmember", ["group_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_groupmember_group_id", table_name="groupmember")
    op.drop_index("ix_groupmember_user_id", table_name="groupmember")
    op.drop_table("groupmember")
