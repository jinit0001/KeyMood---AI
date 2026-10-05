"""emotion module tables

Revision ID: 0003_emotion_module
Revises: 0002_profile_settings
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0003_emotion_module"
down_revision: Union[str, None] = "0002_profile_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_info", pg.JSONB, nullable=True),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "keystroke_features",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", pg.UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("avg_hold_time", sa.Float, nullable=False),
        sa.Column("typing_speed", sa.Float, nullable=False),
        sa.Column("avg_interkey_delay", sa.Float, nullable=False),
        sa.Column("error_rate", sa.Float, nullable=False),
        sa.Column("total_keys", sa.Integer, nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "emotion_baselines",
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("avg_hold_time", sa.Float, nullable=False, server_default="0"),
        sa.Column("typing_speed", sa.Float, nullable=False, server_default="0"),
        sa.Column("avg_interkey_delay", sa.Float, nullable=False, server_default="0"),
        sa.Column("error_rate", sa.Float, nullable=False, server_default="0"),
        sa.Column("sample_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "emotion_predictions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", pg.UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("model_version", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_emotion_predictions_user_id_created_at", "emotion_predictions",
                     ["user_id", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_table("emotion_predictions")
    op.drop_table("emotion_baselines")
    op.drop_table("keystroke_features")
    op.drop_table("sessions")
