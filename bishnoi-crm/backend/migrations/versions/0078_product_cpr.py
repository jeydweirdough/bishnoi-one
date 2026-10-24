"""A product's FDA Certificate of Product Registration (CPR), as Inventory keeps it
(decided 2026-10-24): its number and the day it's valid until, brought over with
the product list (app/inventory.py) and shown in the catalogue. Added in place;
safe to run twice.

Revision ID: 0078
Revises: 0077
"""

from alembic import op
import sqlalchemy as sa

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_products")}
    if "cpr_number" not in have:
        op.add_column("nbcm_products", sa.Column("cpr_number", sa.String(40), nullable=True))
    if "cpr_valid_until" not in have:
        op.add_column("nbcm_products", sa.Column("cpr_valid_until", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_products") as batch:
        batch.drop_column("cpr_valid_until")
        batch.drop_column("cpr_number")
