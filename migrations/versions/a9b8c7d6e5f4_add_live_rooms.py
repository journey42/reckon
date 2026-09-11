"""Add live Q&A room support (additive only).

New columns: group.is_room/closing_note/similarity_threshold/close_at/closed_at,
reckoning.edited_at/removed_at. New tables: roomparticipant, roomswap.

Existing rows are unaffected: is_room defaults to FALSE and every other new
column is nullable.

Revision ID: a9b8c7d6e5f4
Revises: f7a8b9c0d1e2
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a9b8c7d6e5f4"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group", sa.Column("is_room", sa.Boolean(), nullable=False,
                                     server_default=sa.text("false")))
    op.add_column("group", sa.Column("closing_note", sa.Text(), nullable=True))
    op.add_column("group", sa.Column("similarity_threshold", sa.Float(), nullable=True))
    op.add_column("group", sa.Column("close_at", sa.DateTime(), nullable=True))
    op.add_column("group", sa.Column("closed_at", sa.DateTime(), nullable=True))

    op.add_column("reckoning", sa.Column("edited_at", sa.DateTime(), nullable=True))
    op.add_column("reckoning", sa.Column("removed_at", sa.DateTime(), nullable=True))

    op.create_table(
        "roomparticipant",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(),
                  sa.ForeignKey("group.id"), nullable=False, index=True),
        sa.Column("device_hash", sa.String(), nullable=False, unique=True),
        sa.Column("current_answer_id", sa.Integer(),
                  sa.ForeignKey("reckoning.id"), nullable=True),
        sa.Column("supported_answer_id", sa.Integer(),
                  sa.ForeignKey("reckoning.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "roomswap",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(),
                  sa.ForeignKey("group.id"), nullable=False, index=True),
        sa.Column("participant_id", sa.Integer(),
                  sa.ForeignKey("roomparticipant.id"), nullable=False, index=True),
        sa.Column("from_reckoning_id", sa.Integer(),
                  sa.ForeignKey("reckoning.id"), nullable=False),
        sa.Column("to_reckoning_id", sa.Integer(),
                  sa.ForeignKey("reckoning.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("roomswap")
    op.drop_table("roomparticipant")
    op.drop_column("reckoning", "removed_at")
    op.drop_column("reckoning", "edited_at")
    op.drop_column("group", "closed_at")
    op.drop_column("group", "close_at")
    op.drop_column("group", "similarity_threshold")
    op.drop_column("group", "closing_note")
    op.drop_column("group", "is_room")
