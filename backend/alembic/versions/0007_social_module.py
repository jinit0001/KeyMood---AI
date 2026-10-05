"""social module tables

Revision ID: 0007_social_module
Revises: 0006_recommendations_analytics
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0007_social_module"
down_revision: Union[str, None] = "0006_recommendations_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "friendships",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id_a", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("user_id_b", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("user_id_a < user_id_b", name="ck_friendships_ordered"),
        sa.UniqueConstraint("user_id_a", "user_id_b", name="uq_friendships_pair"),
    )

    op.create_table(
        "friend_requests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("sender_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("receiver_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_friend_requests_pending ON friend_requests (sender_id, receiver_id) "
        "WHERE status = 'pending'"
    )


def downgrade() -> None:
    op.drop_table("friend_requests")
    op.drop_table("friendships")
