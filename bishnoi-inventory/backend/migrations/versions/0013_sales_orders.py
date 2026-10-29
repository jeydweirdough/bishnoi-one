"""The Sales app's sales orders (feature plan step 11, agreed 2026-10-29), kept in the Operations service
beside the stock they ship from.

- nbin_sales_orders and their lines: the customer as the CRM has them, the quote it came from, the
  salesperson with their division and team, the payer, the lines at the quote's prices, the tax.
  Waiting for approval, then confirmed (which makes its delivery), delivered or cancelled.
- nbin_orders.sales_order_id: the delivery's sales order (none for an issue to a department).

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "nbin_sales_orders" not in tables:
        op.create_table(
            "nbin_sales_orders",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("number", sa.String(20), nullable=False, unique=True),
            sa.Column("status", sa.String(12), nullable=False, index=True),
            sa.Column("customer_id", sa.String(36), index=True),
            sa.Column("customer_name", sa.String(200), nullable=False),
            sa.Column("customer_address", sa.String(400)),
            sa.Column("customer_tin", sa.String(30)),
            sa.Column("quote_id", sa.String(36), unique=True),
            sa.Column("quote_number", sa.String(30)),
            sa.Column("salesperson_id", sa.String(36), index=True),
            sa.Column("salesperson_name", sa.String(120)),
            sa.Column("division_id", sa.String(36)),
            sa.Column("division_name", sa.String(120)),
            sa.Column("team_id", sa.String(36)),
            sa.Column("team_name", sa.String(120)),
            sa.Column("payer", sa.JSON()),
            sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("nbin_warehouses.id"), nullable=False, index=True),
            sa.Column("scheduled_on", sa.Date()),
            sa.Column("notes", sa.Text()),
            sa.Column("gross_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("discount_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_centavos", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tax", sa.JSON()),
            sa.Column("currency", sa.String(3), nullable=False, server_default="PHP"),
            sa.Column("created_by_id", sa.String(36), sa.ForeignKey("nbin_users.id", ondelete="SET NULL")),
            sa.Column("created_by_name", sa.String(120)),
            sa.Column("decided_by_id", sa.String(36), sa.ForeignKey("nbin_users.id", ondelete="SET NULL")),
            sa.Column("decided_at", sa.DateTime(timezone=True)),
            sa.Column("decision_note", sa.String(500)),
            sa.Column("delivered_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("status IN ('draft', 'pending', 'confirmed', 'delivered', 'rejected', 'cancelled')", name="sales_order_status"),
        )
    if "nbin_sales_order_lines" not in tables:
        op.create_table(
            "nbin_sales_order_lines",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("order_id", sa.String(36), sa.ForeignKey("nbin_sales_orders.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("nbin_products.id"), nullable=False, index=True),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("free_quantity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unit_price", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("discount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("delivered", sa.Integer(), nullable=False, server_default="0"),
            sa.CheckConstraint("quantity > 0", name="sales_order_line_quantity"),
        )
    if "sales_order_id" not in {c["name"] for c in sa.inspect(bind).get_columns("nbin_orders")}:
        with op.batch_alter_table("nbin_orders") as batch:
            batch.add_column(sa.Column("sales_order_id", sa.String(36), sa.ForeignKey("nbin_sales_orders.id", name="nbin_orders_sales_order", ondelete="SET NULL")))
        op.create_index("ix_nbin_orders_sales_order_id", "nbin_orders", ["sales_order_id"])


def downgrade() -> None:
    with op.batch_alter_table("nbin_orders") as batch:
        batch.drop_index("ix_nbin_orders_sales_order_id")
        batch.drop_column("sales_order_id")
    op.drop_table("nbin_sales_order_lines")
    op.drop_table("nbin_sales_orders")
