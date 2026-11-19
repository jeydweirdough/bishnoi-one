"""Packs that can be broken (2026-11-18, owner's Step 4A): which levels of an item may be sold and at what
price, and the unit each sale line was sold in. Stock stays in the base unit. Added in place.

    nbin_products.base_sellable              the base unit may be sold on its own (default yes)
    nbin_product_packagings.sellable, price  this pack may be sold; its own price in centavos (empty = base x quantity)
    nbin_sales_order_lines.packaging_id, unit_name, per   the unit sold (empty = the base unit, per 1)
    nbin_order_lines.sold_as                 "2 Boxes of 10", for the delivery note

Revision ID: 0028
Revises: 0027
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

COLUMNS = (
    ("nbin_products", sa.Column("base_sellable", sa.Boolean(), nullable=False, server_default=sa.true())),
    ("nbin_product_packagings", sa.Column("sellable", sa.Boolean(), nullable=False, server_default=sa.true())),
    ("nbin_product_packagings", sa.Column("price", sa.Integer(), nullable=True)),
    ("nbin_sales_order_lines", sa.Column("packaging_id", sa.String(36), nullable=True)),
    ("nbin_sales_order_lines", sa.Column("unit_name", sa.String(40), nullable=True)),
    ("nbin_sales_order_lines", sa.Column("per", sa.Integer(), nullable=False, server_default="1")),
    ("nbin_order_lines", sa.Column("sold_as", sa.String(80), nullable=True)),
)


def upgrade() -> None:
    for table, column in COLUMNS:
        op.add_column(table, column)


def downgrade() -> None:
    for table, column in reversed(COLUMNS):
        op.drop_column(table, column.name)
