"""recommendations + analytics tables

Revision ID: 0006_recommendations_analytics
Revises: 0005_journal_module
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0006_recommendations_analytics"
down_revision: Union[str, None] = "0005_journal_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("payload", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_recommendations_user_shown", "recommendations", ["user_id", "shown_at"])

    op.create_table(
        "recommendation_feedback",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("recommendation_id", pg.UUID(as_uuid=True), sa.ForeignKey("recommendations.id"), nullable=False),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reaction", sa.String(15), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "analytics_snapshots",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("metrics", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "period", "period_start", name="uq_analytics_snapshot"),
    )

    op.create_table(
        "wellness_scores",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("contributing_factors", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_wellness_scores_user_computed", "wellness_scores", ["user_id", sa.text("computed_at DESC")])


def downgrade() -> None:
    op.drop_table("wellness_scores")
    op.drop_table("analytics_snapshots")
    op.drop_table("recommendation_feedback")
    op.drop_table("recommendations")
