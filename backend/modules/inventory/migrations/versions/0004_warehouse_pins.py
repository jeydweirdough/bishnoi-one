"""Each warehouse can have its place on the map (latitude and longitude), so
transfers between warehouses can be drawn as routes. Empty until someone sets
the pin, or finds it from the address.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbin_warehouses")}
    with op.batch_alter_table("nbin_warehouses") as batch:
        if "latitude" not in columns:
            batch.add_column(sa.Column("latitude", sa.Float(), nullable=True))
        if "longitude" not in columns:
            batch.add_column(sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbin_warehouses") as batch:
        batch.drop_column("longitude")
        batch.drop_column("latitude")
