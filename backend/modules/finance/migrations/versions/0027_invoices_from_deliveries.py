"""Automatic invoicing (feature plan step 13, 2026-10-29): a customer's delivery leaving the warehouse
(delivery.done) becomes its invoice here.

- nbfi_invoices: the delivery it bills (once each: unique), its sales order, and why it is still a draft
  when it couldn't be issued by itself (no invoice numbers left, the tax registration incomplete…).
- nbfi_ledger_settings.auto_invoice: "issue" (issued at once, numbered from the series) or "draft"
  (made as a draft for Finance to check and issue).

Revision ID: 0027
Revises: 0026
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

INVOICE_COLUMNS = (("delivery_id", sa.String(36)), ("delivery_number", sa.String(30)), ("sales_order_id", sa.String(36)),
                   ("sales_order_number", sa.String(30)), ("attention", sa.String(300)))


def upgrade() -> None:
    # In place, never rebuilding a table: on SQLite a rebuild drops what points at it (tests/test_migrate.py).
    bind = op.get_bind()
    have = {c["name"] for c in sa.inspect(bind).get_columns("nbfi_invoices")}
    for name, kind in INVOICE_COLUMNS:
        if name not in have:
            op.add_column("nbfi_invoices", sa.Column(name, kind))
    indexes = {i["name"] for i in sa.inspect(bind).get_indexes("nbfi_invoices")}
    if "nbfi_invoices_delivery" not in indexes:
        op.create_index("nbfi_invoices_delivery", "nbfi_invoices", ["delivery_id"], unique=True)
    if "ix_nbfi_invoices_sales_order_id" not in indexes:
        op.create_index("ix_nbfi_invoices_sales_order_id", "nbfi_invoices", ["sales_order_id"])
    if "auto_invoice" not in {c["name"] for c in sa.inspect(bind).get_columns("nbfi_ledger_settings")}:
        op.add_column("nbfi_ledger_settings", sa.Column("auto_invoice", sa.String(8), nullable=False, server_default="issue"))


def downgrade() -> None:
    op.drop_index("ix_nbfi_invoices_sales_order_id", "nbfi_invoices")
    op.drop_index("nbfi_invoices_delivery", "nbfi_invoices")
    with op.batch_alter_table("nbfi_ledger_settings") as batch:
        batch.drop_column("auto_invoice")
    with op.batch_alter_table("nbfi_invoices") as batch:
        for name, _ in reversed(INVOICE_COLUMNS):
            batch.drop_column(name)
