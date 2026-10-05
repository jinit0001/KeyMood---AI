"""sos / safety module tables

Revision ID: 0004_sos_module
Revises: 0003_emotion_module

Append-only enforcement for risk_events/risk_escalations uses a
BEFORE UPDATE trigger, not REVOKE UPDATE — a bare REVOKE breaks
FK-referencing inserts (Postgres row-lock checks need UPDATE privilege
on the referenced table), confirmed empirically in an earlier build.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0004_sos_module"
down_revision: Union[str, None] = "0003_emotion_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "emergency_contacts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("relationship", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "guardians",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("guardian_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("guardian_contact_id", pg.UUID(as_uuid=True), sa.ForeignKey("emergency_contacts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "guardian_consents",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("guardian_id", pg.UUID(as_uuid=True), sa.ForeignKey("guardians.id"), nullable=False),
        sa.Column("consent_given", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "risk_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("risk_level", sa.String(15), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_risk_events_user_id", "risk_events", ["user_id", sa.text("created_at DESC")])

    op.create_table(
        "risk_escalations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("risk_event_id", pg.UUID(as_uuid=True), sa.ForeignKey("risk_events.id"), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "sos_notifications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("escalation_id", pg.UUID(as_uuid=True), sa.ForeignKey("risk_escalations.id"), nullable=False),
        sa.Column("guardian_id", pg.UUID(as_uuid=True), sa.ForeignKey("guardians.id"), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("delivery_status", sa.String(15), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION reject_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'append-only table: % rows cannot be updated', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("CREATE TRIGGER risk_events_append_only BEFORE UPDATE ON risk_events FOR EACH ROW EXECUTE FUNCTION reject_update()")
    op.execute("CREATE TRIGGER risk_escalations_append_only BEFORE UPDATE ON risk_escalations FOR EACH ROW EXECUTE FUNCTION reject_update()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS risk_escalations_append_only ON risk_escalations")
    op.execute("DROP TRIGGER IF EXISTS risk_events_append_only ON risk_events")
    op.execute("DROP FUNCTION IF EXISTS reject_update()")
    op.drop_table("sos_notifications")
    op.drop_table("risk_escalations")
    op.drop_table("risk_events")
    op.drop_table("guardian_consents")
    op.drop_table("guardians")
    op.drop_table("emergency_contacts")
