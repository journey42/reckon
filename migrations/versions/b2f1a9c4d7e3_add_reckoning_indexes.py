"""add reckoning indexes

Revision ID: b2f1a9c4d7e3
Revises: 5c4374b3a58f
Create Date: 2026-06-22 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "b2f1a9c4d7e3"
down_revision: Union[str, Sequence[str], None] = "5c4374b3a58f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass