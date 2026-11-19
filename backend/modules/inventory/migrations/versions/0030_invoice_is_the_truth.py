"""The invoice is the order's source of truth (2026-11-18, owner's Step 4D): once Finance issues the invoice for a
sales order's delivery, the order keeps the invoice's figures and shows them; a void clears them until the reissue.
Added in place.

    nbin_sales_orders.invoice_state      issued / paid / voided (empty: not invoiced)
    nbin_sales_orders.invoice_gross, invoice_discount, invoice_tax   centavos, as the invoice shows them
    nbin_sales_orders.invoice_lines      the invoice's lines (description, quantity, price, discount, VAT, total)
    nbin_sales_orders.invoice_note       why it was voided

Orders invoiced before this keep invoice_total and are marked issued (or paid) here.

Revision ID: 0030
Revises: 0029
"""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

COLUMNS = (
    sa.Column("invoice_state", sa.String(10), nullable=True),
    sa.Column("invoice_gross", sa.Integer(), nullable=True),
    sa.Column("invoice_discount", sa.Integer(), nullable=True),
    sa.Column("invoice_tax", sa.Integer(), nullable=True),
    sa.Column("invoice_lines", sa.JSON(), nullable=True),
    sa.Column("invoice_note", sa.String(300), nullable=True),
)


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column("nbin_sales_orders", column)
    op.execute("UPDATE nbin_sales_orders SET invoice_state = CASE WHEN paid_at IS NOT NULL THEN 'paid' ELSE 'issued' END WHERE invoice_id IS NOT NULL")


def downgrade() -> None:
    for column in reversed(COLUMNS):
        op.drop_column("nbin_sales_orders", column.name)
