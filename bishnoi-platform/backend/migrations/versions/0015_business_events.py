"""Business events (feature plan step 7, decision 12): what the apps tell each other, through here.

- nbpl_events: each event once (its id is the one the sending app gave it), with its company, kind,
  data and when it happened.
- nbpl_event_deliveries: one per app that takes it: pending (next try at), delivered, stuck (after
  the tries ran out; an operator retries or skips it) or skipped.

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "nbpl_events" not in tables:
        op.create_table(
            "nbpl_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("source", sa.String(40), nullable=False),
            sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("kind", sa.String(60), nullable=False, index=True),
            sa.Column("data", sa.JSON(), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "nbpl_event_deliveries" not in tables:
        op.create_table(
            "nbpl_event_deliveries",
            sa.Column("event_id", sa.String(36), sa.ForeignKey("nbpl_events.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("target", sa.String(40), primary_key=True),
            sa.Column("status", sa.String(12), nullable=False, index=True),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_at", sa.DateTime(timezone=True), index=True),
            sa.Column("last_error", sa.String(300)),
            sa.Column("delivered_at", sa.DateTime(timezone=True)),
            sa.CheckConstraint("status IN ('pending', 'delivered', 'stuck', 'skipped')", name="nbpl_delivery_status"),
        )


def downgrade() -> None:
    op.drop_table("nbpl_event_deliveries")
    op.drop_table("nbpl_events")
