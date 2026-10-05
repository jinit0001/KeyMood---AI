"""profile & settings module tables

Revision ID: 0002_profile_settings
Revises: 0001_auth_module
Create Date: 2026-09-07

Creates: user_settings, data_export_requests. user_profiles already
exists from 0001 (Auth INSERTs the initial row; this module owns full
read/update over it via SqlProfileRepository — no schema change needed
there). Both new tables are gap-fills not present in DATABASE.md — see
app/domain/profile/entities.py docstrings for why.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0002_profile_settings"
down_revision: Union[str, None] = "0001_auth_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("privacy", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notifications", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ai_preferences", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "data_export_requests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default="pending"),
        sa.Column("download_url", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_data_export_requests_user_id", "data_export_requests", ["user_id"])


def downgrade() -> None:
    op.drop_table("data_export_requests")
    op.drop_table("user_settings")
