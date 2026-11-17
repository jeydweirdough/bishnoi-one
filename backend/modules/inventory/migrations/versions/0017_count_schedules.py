"""Scheduled cycle counts (feature plan step 14b, 2026-10-29).

- nbin_count_schedules: a count that comes round every so many days, for one warehouse (and one category,
  when set), with the day it is next due.
- nbin_counts.schedule_id: the schedule a count was started from; approving it sets the next due day.

Added in place: on SQLite a table rebuild drops what points at it.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "nbin_count_schedules" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "nbin_count_schedules",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("nbin_warehouses.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("category_id", sa.String(36), sa.ForeignKey("nbin_categories.id", ondelete="SET NULL")),
            sa.Column("every_days", sa.Integer(), nullable=False),
            sa.Column("next_on", sa.Date(), nullable=False, index=True),
            sa.Column("last_counted_on", sa.Date()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbin_users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("every_days > 0", name="count_schedule_every"),
        )
    if "schedule_id" not in {c["name"] for c in sa.inspect(bind).get_columns("nbin_counts")}:
        op.add_column("nbin_counts", sa.Column("schedule_id", sa.String(36)))
        op.create_index("ix_nbin_counts_schedule_id", "nbin_counts", ["schedule_id"])


def downgrade() -> None:
    op.drop_index("ix_nbin_counts_schedule_id", "nbin_counts")
    with op.batch_alter_table("nbin_counts") as batch:
        batch.drop_column("schedule_id")
    op.drop_table("nbin_count_schedules")
