"""journal module tables

Revision ID: 0005_journal_module
Revises: 0004_sos_module
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0005_journal_module"
down_revision: Union[str, None] = "0004_sos_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "journal_entries",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("linked_emotion_prediction_id", pg.UUID(as_uuid=True), sa.ForeignKey("emotion_predictions.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_journal_entries_user_id", "journal_entries", ["user_id", sa.text("created_at DESC")])
    op.execute("CREATE INDEX ix_journal_entries_fts ON journal_entries USING GIN (to_tsvector('english', content))")

    op.create_table(
        "journal_tags",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_id", pg.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("tag", sa.String(40), nullable=False),
    )
    op.create_index("ix_journal_tags_entry_id", "journal_tags", ["entry_id"])


def downgrade() -> None:
    op.drop_table("journal_tags")
    op.drop_table("journal_entries")
