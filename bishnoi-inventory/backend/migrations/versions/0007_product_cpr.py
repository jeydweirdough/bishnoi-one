"""A product's Certificate of Product Registration (CPR) from the Philippine FDA:
its number and the day it's valid until (decided 2026-10-24, app/cpr.py).
Added in place, never by rebuilding the table; safe to run twice.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    have = {c["name"] for c in inspector.get_columns("nbin_products")}
    if "cpr_number" not in have:
        op.add_column("nbin_products", sa.Column("cpr_number", sa.String(40), nullable=True))
    if "cpr_valid_until" not in have:
        op.add_column("nbin_products", sa.Column("cpr_valid_until", sa.Date(), nullable=True))
    if "ix_nbin_products_cpr_number" not in {i["name"] for i in inspector.get_indexes("nbin_products")}:
        op.create_index("ix_nbin_products_cpr_number", "nbin_products", ["cpr_number"])


def downgrade() -> None:
    op.drop_index("ix_nbin_products_cpr_number", table_name="nbin_products")
    with op.batch_alter_table("nbin_products") as batch:
        batch.drop_column("cpr_valid_until")
        batch.drop_column("cpr_number")
