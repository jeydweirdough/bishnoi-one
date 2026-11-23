"""A sales order carries what its quote carried (2026-11-23, owner: the quotation is the basis of the sales order, and a
sales order made directly is priced the same way). Added in place; no rows change.

    nbin_sales_orders.source                  quote (raised from a CRM quote) / direct (made with the quote form) / typed
                                              (empty: older orders, quote when quote_id is set, typed otherwise)
    nbin_sales_orders.price_type, price_type_name, rx
    nbin_sales_orders.promo_discount_centavos  the promos' share of discount_centavos (the rest is extra discounts)
    nbin_sales_orders.customer_email, customer_phone
    nbin_sales_orders.letter                  the guarantee letter: number, issuedOn, amountCentavos, file name
    nbin_sales_orders.letter_file, letter_file_type   a direct order's letter itself (a quote's stays with the quote)
    nbin_sales_orders.approval_reasons        why it needs approval, as the CRM priced it (price, discount, margin, s2_license, rx, credit)
    nbin_sales_orders.warnings                the pricing's warnings (CLIDP, S-2) for the approvers
    nbin_sales_orders.terms                   the quote's terms
    nbin_sales_order_lines.promo_name, promo_discount, extra_discount, discount_kind, discount_value, bundle_name

Revision ID: 0032
Revises: 0031
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

ORDERS = (
    sa.Column("source", sa.String(10), nullable=True),
    sa.Column("price_type", sa.String(40), nullable=True),
    sa.Column("price_type_name", sa.String(120), nullable=True),
    sa.Column("rx", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("promo_discount_centavos", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("customer_email", sa.String(254), nullable=True),
    sa.Column("customer_phone", sa.String(60), nullable=True),
    sa.Column("letter", sa.JSON(), nullable=True),
    sa.Column("letter_file", sa.LargeBinary(), nullable=True),
    sa.Column("letter_file_type", sa.String(60), nullable=True),
    sa.Column("approval_reasons", sa.JSON(), nullable=True),
    sa.Column("warnings", sa.JSON(), nullable=True),
    sa.Column("terms", sa.Text(), nullable=True),
)
LINES = (
    sa.Column("promo_name", sa.String(160), nullable=True),
    sa.Column("promo_discount", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("extra_discount", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("discount_kind", sa.String(10), nullable=True),
    sa.Column("discount_value", sa.Integer(), nullable=True),
    sa.Column("bundle_name", sa.String(160), nullable=True),
)


def upgrade() -> None:
    for column in ORDERS:
        op.add_column("nbin_sales_orders", column)
    for column in LINES:
        op.add_column("nbin_sales_order_lines", column)


def downgrade() -> None:
    for column in reversed(LINES):
        op.drop_column("nbin_sales_order_lines", column.name)
    for column in reversed(ORDERS):
        op.drop_column("nbin_sales_orders", column.name)
