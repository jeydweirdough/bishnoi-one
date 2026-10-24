"""A calendar, switched on per person, with reminders.

- nbfi_users.calendar_on: whether this person has the calendar (off for
  everyone until an Administrator switches it on).
- nbfi_calendar_events: each person's own events (a deadline, a cut-off),
  which may repeat and remind some working days before.
- nbfi_calendar_shares: who else sees an event (and may mark it done).
- nbfi_calendar_done: which dates of an event are done.

Decided 2026-10-22 (Plans/Plan - Finance calendar). Written as 0013 on our
branch; renumbered 0014 after main's 0012 (invoice salesperson).

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "calendar_on" not in {c["name"] for c in inspector.get_columns("nbfi_users")}:
        with op.batch_alter_table("nbfi_users") as batch:
            batch.add_column(sa.Column("calendar_on", sa.Boolean(), nullable=False, server_default=sa.false()))
    tables = set(inspector.get_table_names())
    if "nbfi_calendar_events" not in tables:
        op.create_table(
            "nbfi_calendar_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("notes", sa.String(1000), nullable=True),
            sa.Column("starts_on", sa.Date(), nullable=False),
            sa.Column("at_time", sa.String(5), nullable=True),
            sa.Column("repeat", sa.String(16), nullable=False, server_default="none"),
            sa.Column("until", sa.Date(), nullable=True),
            sa.Column("remind_days", sa.Integer(), nullable=True),
            sa.Column("link", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("repeat IN ('none', 'monthly', 'quarterly', 'yearly', 'twice_monthly')", name="calendar_repeat"),
        )
        op.create_index("ix_nbfi_calendar_events_owner_id", "nbfi_calendar_events", ["owner_id"])
    if "nbfi_calendar_shares" not in tables:
        op.create_table(
            "nbfi_calendar_shares",
            sa.Column("event_id", sa.String(36), sa.ForeignKey("nbfi_calendar_events.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="CASCADE"), primary_key=True),
        )
        op.create_index("ix_nbfi_calendar_shares_user_id", "nbfi_calendar_shares", ["user_id"])
    if "nbfi_calendar_done" not in tables:
        op.create_table(
            "nbfi_calendar_done",
            sa.Column("event_id", sa.String(36), sa.ForeignKey("nbfi_calendar_events.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("occurs_on", sa.Date(), primary_key=True),
            sa.Column("done_by", sa.String(120), nullable=False),
            sa.Column("done_by_id", sa.String(36), sa.ForeignKey("nbfi_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("done_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("nbfi_calendar_done")
    op.drop_table("nbfi_calendar_shares")
    op.drop_table("nbfi_calendar_events")
    with op.batch_alter_table("nbfi_users") as batch:
        batch.drop_column("calendar_on")
