"""AI companion module tables

Revision ID: 0009_companion_module
Revises: 0008_messaging_module
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_companion_module"
down_revision = "0008_messaging_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companion_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "companion_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companion_sessions.id"), nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("flagged_crisis", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_companion_messages_session_created", "companion_messages", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_companion_messages_session_created", table_name="companion_messages")
    op.drop_table("companion_messages")
    op.drop_table("companion_sessions")
