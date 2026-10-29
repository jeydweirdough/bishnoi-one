"""Replenishment (feature plan step 15a, 2026-10-29): refill worked out from use and lead time.

- nbin_replenishment_settings (one row): safety days added to every lead time, the lead time when the vendor
  has none, how many days of use the daily average looks back on, and whether draft purchase orders are made
  by themselves each night.
- nbin_purchase_orders.replenishment: made by replenishment (by hand from its page, or at night).

Added in place: on SQLite a table rebuild drops what points at it.

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "nbin_replenishment_settings" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "nbin_replenishment_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("safety_days", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("default_lead_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("history_days", sa.Integer(), nullable=False, server_default="90"),
            sa.Column("automatic", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_run_at", sa.DateTime(timezone=True)),
            sa.CheckConstraint("id = 1", name="one_replenishment_settings"),
        )
    if "replenishment" not in {c["name"] for c in sa.inspect(bind).get_columns("nbin_purchase_orders")}:
        op.add_column("nbin_purchase_orders", sa.Column("replenishment", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("nbin_purchase_orders") as batch:
        batch.drop_column("replenishment")
    op.drop_table("nbin_replenishment_settings")
