"""add debate table

Revision ID: c3d4e5f6a7b8
Revises: b2f1a9c4d7e3
Create Date: 2026-06-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2f1a9c4d7e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "debate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("concept_id", sa.Integer(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("intro", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["concept_id"], ["reckoning.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_debate_slug", "debate", ["slug"], unique=True)
    op.create_index("ix_debate_concept_id", "debate", ["concept_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_debate_concept_id", table_name="debate")
    op.drop_index("ix_debate_slug", table_name="debate")
    op.drop_table("debate")
