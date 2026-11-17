"""An assistance application can be for several GetMeds products: a list, not one.

Revision ID: 0069
Revises: 0068
"""

import json

from alembic import op
import sqlalchemy as sa

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_assistance")}
    if "products" in columns:
        return  # made fresh from the models
    with op.batch_alter_table("nbcm_assistance") as batch:
        batch.add_column(sa.Column("products", sa.JSON(), nullable=True))
    table = sa.table("nbcm_assistance", sa.column("id", sa.String), sa.column("product_id", sa.String), sa.column("product_name", sa.String), sa.column("products", sa.JSON))
    connection = op.get_bind()
    for id_, pid, name in connection.execute(sa.select(table.c.id, table.c.product_id, table.c.product_name)).all():
        connection.execute(table.update().where(table.c.id == id_).values(products=[{"id": pid, "name": name}]))
    with op.batch_alter_table("nbcm_assistance") as batch:
        batch.drop_column("product_id")
        batch.drop_column("product_name")


def downgrade() -> None:
    with op.batch_alter_table("nbcm_assistance") as batch:
        batch.add_column(sa.Column("product_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("product_name", sa.String(200), nullable=True))
    table = sa.table("nbcm_assistance", sa.column("id", sa.String), sa.column("product_id", sa.String), sa.column("product_name", sa.String), sa.column("products", sa.JSON))
    connection = op.get_bind()
    for id_, products in connection.execute(sa.select(table.c.id, table.c.products)).all():
        first = (json.loads(products) if isinstance(products, str) else products or [{}])[0]
        connection.execute(table.update().where(table.c.id == id_).values(product_id=first.get("id"), product_name=first.get("name") or ""))
    with op.batch_alter_table("nbcm_assistance") as batch:
        batch.drop_column("products")
