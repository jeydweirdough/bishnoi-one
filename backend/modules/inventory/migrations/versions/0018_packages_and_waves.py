"""Packages and wave picking (feature plan step 14d, 2026-10-29): pick → pack → ship.

- nbin_packages (+ lines): a delivery's boxes, numbered, each with what is in it (from its lines), its weight.
- nbin_waves: several held deliveries from one warehouse picked together from one pick list.
- nbin_orders.wave_id: the wave a delivery is picked in.

Added in place: on SQLite a table rebuild drops what points at it.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "nbin_packages" not in tables:
        op.create_table(
            "nbin_packages",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("number", sa.String(20), nullable=False, unique=True),
            sa.Column("order_id", sa.String(36), sa.ForeignKey("nbin_orders.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("weight_grams", sa.Integer()),
            sa.Column("notes", sa.String(300)),
            sa.Column("packed_by_id", sa.String(36), sa.ForeignKey("nbin_users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "nbin_package_lines" not in tables:
        op.create_table(
            "nbin_package_lines",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("package_id", sa.String(36), sa.ForeignKey("nbin_packages.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("order_line_id", sa.String(36), sa.ForeignKey("nbin_order_lines.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.CheckConstraint("quantity > 0", name="package_line_quantity"),
        )
    if "nbin_waves" not in tables:
        op.create_table(
            "nbin_waves",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("number", sa.String(20), nullable=False, unique=True),
            sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("nbin_warehouses.id"), nullable=False, index=True),
            sa.Column("status", sa.String(10), nullable=False, index=True),
            sa.Column("notes", sa.String(300)),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbin_users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("done_at", sa.DateTime(timezone=True)),
            sa.CheckConstraint("status IN ('open', 'done')", name="wave_status"),
        )
    if "wave_id" not in {c["name"] for c in sa.inspect(bind).get_columns("nbin_orders")}:
        op.add_column("nbin_orders", sa.Column("wave_id", sa.String(36)))
        op.create_index("ix_nbin_orders_wave_id", "nbin_orders", ["wave_id"])


def downgrade() -> None:
    op.drop_index("ix_nbin_orders_wave_id", "nbin_orders")
    with op.batch_alter_table("nbin_orders") as batch:
        batch.drop_column("wave_id")
    op.drop_table("nbin_waves")
    op.drop_table("nbin_package_lines")
    op.drop_table("nbin_packages")
