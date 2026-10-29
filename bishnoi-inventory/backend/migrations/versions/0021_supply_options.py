"""Order-on-demand, dropshipping, consignment and documents with products (feature plan step 15b–15e, 2026-10-29).

- nbin_purchase_orders.sales_order_id: the sales order it was raised for (order-on-demand, 15b; dropshipping, 15c).
- nbin_purchase_orders.dropship + ship_to_name/address: the vendor ships straight to our customer (15c).
- nbin_sales_orders.dropship: this order goes from the vendor to the customer, not from our warehouse (15c).
- nbin_locations.consignment_supplier_id: a vendor's consignment stock is kept in its own location (15d).
- nbin_receipts.consignment: received on consignment: the vendor's until it sells (15d).
- nbin_replenishment_settings.order_on_demand: raise draft purchase orders for what an approved sales order lacks (15b).
- nbin_product_documents: files kept with an item (certificate of analysis, leaflet, CPR) and whether each goes
  with every sale (15e).

Added in place: on SQLite a table rebuild drops what points at it.

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

ADD = (
    ("nbin_purchase_orders", "sales_order_id", sa.String(36), None),
    ("nbin_purchase_orders", "dropship", sa.Boolean(), sa.false()),
    ("nbin_purchase_orders", "ship_to_name", sa.String(200), None),
    ("nbin_purchase_orders", "ship_to_address", sa.String(400), None),
    ("nbin_sales_orders", "dropship", sa.Boolean(), sa.false()),
    ("nbin_locations", "consignment_supplier_id", sa.String(36), None),
    ("nbin_receipts", "consignment", sa.Boolean(), sa.false()),
    ("nbin_replenishment_settings", "order_on_demand", sa.Boolean(), sa.true()),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table, name, kind, default in ADD:
        if name not in {c["name"] for c in sa.inspect(bind).get_columns(table)}:
            op.add_column(table, sa.Column(name, kind, nullable=default is None, **({"server_default": default} if default is not None else {})))
    if "ix_nbin_purchase_orders_sales_order_id" not in {i["name"] for i in sa.inspect(bind).get_indexes("nbin_purchase_orders")}:
        op.create_index("ix_nbin_purchase_orders_sales_order_id", "nbin_purchase_orders", ["sales_order_id"])
    if "nbin_product_documents" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "nbin_product_documents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("nbin_products.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("file_name", sa.String(200), nullable=False),
            sa.Column("content_type", sa.String(80), nullable=False),
            sa.Column("data", sa.LargeBinary(), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("send_with_sales", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("nbin_product_documents")
    op.drop_index("ix_nbin_purchase_orders_sales_order_id", "nbin_purchase_orders")
    for table, name, _, _ in reversed(ADD):
        with op.batch_alter_table(table) as batch:
            batch.drop_column(name)
