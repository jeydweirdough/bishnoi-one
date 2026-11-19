"""Quality checks on receipt (feature plan step 14a, 2026-10-29): receive → check → store.

- nbin_warehouses.quality_check: this warehouse checks what it receives before it can be used.
- nbin_stock.on_hold: received and on hand, waiting for its quality check: not available to reserve or pick.
- nbin_quality_checks (+ lines): one per receipt into such a warehouse: what passed (released for use) and
  what failed (put aside as damaged, with why).

Added in place: on SQLite a table rebuild drops what points at it.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "quality_check" not in {c["name"] for c in sa.inspect(bind).get_columns("nbin_warehouses")}:
        op.add_column("nbin_warehouses", sa.Column("quality_check", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "on_hold" not in {c["name"] for c in sa.inspect(bind).get_columns("nbin_stock")}:
        op.add_column("nbin_stock", sa.Column("on_hold", sa.Integer(), nullable=False, server_default="0"))
    tables = set(sa.inspect(bind).get_table_names())
    if "nbin_quality_checks" not in tables:
        op.create_table(
            "nbin_quality_checks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("number", sa.String(20), nullable=False, unique=True),
            sa.Column("receipt_id", sa.String(36), sa.ForeignKey("nbin_receipts.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("nbin_warehouses.id"), nullable=False, index=True),
            sa.Column("status", sa.String(10), nullable=False, index=True),
            sa.Column("notes", sa.Text()),
            sa.Column("checked_by_id", sa.String(36), sa.ForeignKey("nbin_users.id", ondelete="SET NULL")),
            sa.Column("checked_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('waiting', 'done')", name="quality_check_status"),
        )
    if "nbin_quality_check_lines" not in tables:
        op.create_table(
            "nbin_quality_check_lines",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("check_id", sa.String(36), sa.ForeignKey("nbin_quality_checks.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("nbin_products.id"), nullable=False),
            sa.Column("location_id", sa.String(36), sa.ForeignKey("nbin_locations.id"), nullable=False),
            sa.Column("batch_id", sa.String(36), sa.ForeignKey("nbin_batches.id", ondelete="SET NULL")),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("passed", sa.Integer()),
            sa.Column("failed", sa.Integer()),
            sa.Column("reason", sa.String(40)),
            sa.Column("note", sa.String(300)),
        )


def downgrade() -> None:
    op.drop_table("nbin_quality_check_lines")
    op.drop_table("nbin_quality_checks")
    with op.batch_alter_table("nbin_stock") as batch:
        batch.drop_column("on_hold")
    with op.batch_alter_table("nbin_warehouses") as batch:
        batch.drop_column("quality_check")
