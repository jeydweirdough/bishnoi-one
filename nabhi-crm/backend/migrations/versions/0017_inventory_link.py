"""The product list from Nabhi Inventory.

- nbcm_products.inventory_id: the Inventory product it is.
- nbcm_sales_settings.inventory_synced_at, inventory_error: the last sync.

Each step only if it isn't done yet, like 0015.

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = lambda table: {c["name"] for c in inspector.get_columns(table)}  # noqa: E731

    if "inventory_id" not in columns("nbcm_products"):
        with op.batch_alter_table("nbcm_products") as batch:
            batch.add_column(sa.Column("inventory_id", sa.String(36)))
            batch.create_unique_constraint("uq_nbcm_products_inventory_id", ["inventory_id"])

    have = columns("nbcm_sales_settings")
    with op.batch_alter_table("nbcm_sales_settings") as batch:
        if "inventory_synced_at" not in have:
            batch.add_column(sa.Column("inventory_synced_at", sa.DateTime(timezone=True)))
        if "inventory_error" not in have:
            batch.add_column(sa.Column("inventory_error", sa.String(300)))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_sales_settings") as batch:
        batch.drop_column("inventory_error")
        batch.drop_column("inventory_synced_at")
    with op.batch_alter_table("nbcm_products") as batch:
        batch.drop_constraint("uq_nbcm_products_inventory_id", type_="unique")
        batch.drop_column("inventory_id")
