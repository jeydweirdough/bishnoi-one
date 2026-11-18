"""Team prices and special prices on approval slips (2026-11-18, Step 4C): on nbcm_product_prices and nbcm_team_prices,
slip_batch_id (the save a price was proposed in, the slip's record), slip_state and slip_held_centavos (what Finance
approved while the slip waits). Added in place; no rows change.

Revision ID: 0086
Revises: 0085
"""

import sqlalchemy as sa
from alembic import op

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None

TABLES = ("nbcm_product_prices", "nbcm_team_prices")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in TABLES:
        have = {c["name"] for c in inspector.get_columns(table)}
        if "slip_batch_id" not in have:
            op.add_column(table, sa.Column("slip_batch_id", sa.String(36), nullable=True))
            op.create_index(f"ix_{table}_slip_batch_id", table, ["slip_batch_id"])
        if "slip_state" not in have:
            op.add_column(table, sa.Column("slip_state", sa.String(10), nullable=True))
        if "slip_held_centavos" not in have:
            op.add_column(table, sa.Column("slip_held_centavos", sa.Integer(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_slip_batch_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_column("slip_held_centavos")
            batch.drop_column("slip_state")
            batch.drop_column("slip_batch_id")
