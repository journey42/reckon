"""Add the outbox revision to roomparticipant (additive only).

`intent_version` is a server-issued counter for one device's queue in one room.
The offline outbox stamps each queued write with the next revision; a write
whose revision is not newer than the server's current one is a replay or a
superseded intent and must not overwrite newer words. This replaces comparing
the device's clock against the server's, which phones disagree about routinely.

Existing rows default to 0, so a device with an empty queue starts at the
bottom of the sequence and the next write becomes revision 1.

Revision ID: c9d1e2f3a4b5
Revises: a9b8c7d6e5f4
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa


revision = "c9d1e2f3a4b5"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roomparticipant",
        sa.Column(
            "intent_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("roomparticipant", "intent_version")
