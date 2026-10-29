"""Automatic invoicing (feature plan step 13, 2026-10-29).

- nbin_sales_order_lines.vat_category: the product's VAT category as the CRM gave it with the quote,
  for the invoice Finance makes from the delivery ("standard" when typed here).
- nbin_sales_orders: the invoice Finance made from its delivery (invoice.issued) and when it was paid in
  full (invoice.paid): quote → order → delivered → invoiced → paid, with the days between.

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

ORDER_COLUMNS = (("invoice_id", sa.String(36)), ("invoice_number", sa.String(30)), ("invoiced_at", sa.DateTime(timezone=True)),
                 ("invoice_total", sa.Integer()), ("paid_at", sa.DateTime(timezone=True)))


def upgrade() -> None:
    # In place, never rebuilding a table: on SQLite a rebuild drops what points at it (deliveries' sales_order_id).
    bind = op.get_bind()
    if "vat_category" not in {c["name"] for c in sa.inspect(bind).get_columns("nbin_sales_order_lines")}:
        op.add_column("nbin_sales_order_lines", sa.Column("vat_category", sa.String(20), nullable=False, server_default="standard"))
    have = {c["name"] for c in sa.inspect(bind).get_columns("nbin_sales_orders")}
    for name, kind in ORDER_COLUMNS:
        if name not in have:
            op.add_column("nbin_sales_orders", sa.Column(name, kind))


def downgrade() -> None:
    with op.batch_alter_table("nbin_sales_orders") as batch:
        for name, _ in reversed(ORDER_COLUMNS):
            batch.drop_column(name)
    with op.batch_alter_table("nbin_sales_order_lines") as batch:
        batch.drop_column("vat_category")
