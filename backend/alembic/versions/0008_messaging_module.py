"""messaging module tables

media_attachments exists only to give messages.media_id a real FK target,
per DATABASE.md parity -- there is no upload endpoint in this module.

Revision ID: 0008_messaging_module
Revises: 0007_social_module
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_messaging_module"
down_revision = "0007_social_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("uploader_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("storage_url", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "conversation_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_conversation_members_active",
        "conversation_members",
        ["conversation_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("media_attachments.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", sa.text("created_at DESC")]
    )

    op.create_table(
        "message_reads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_message_reads", "message_reads", ["message_id", "user_id"])


def downgrade() -> None:
    op.drop_table("message_reads")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_index("uq_conversation_members_active", table_name="conversation_members")
    op.drop_table("conversation_members")
    op.drop_table("conversations")
    op.drop_table("media_attachments")
