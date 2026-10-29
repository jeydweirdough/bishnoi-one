"""Units with conversions (feature plan step 14e, 2026-10-29): an item's packaging levels.

- nbin_product_packagings: a pack of the item (Box, Strip, Case…) and how many of its base unit it holds, with
  its own barcode when it has one. Stock stays in the base unit; forms convert what is typed in packs, scanning
  a pack's barcode counts the whole pack, and quantities can be shown in packs too.

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbin_product_packagings" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "nbin_product_packagings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("product_id", sa.String(36), sa.ForeignKey("nbin_products.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name", sa.String(40), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("barcode", sa.String(64), index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("quantity > 1", name="packaging_quantity"),
            sa.UniqueConstraint("product_id", "name", name="packaging_name"),
        )


def downgrade() -> None:
    op.drop_table("nbin_product_packagings")
