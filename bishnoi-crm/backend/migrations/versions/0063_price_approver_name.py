"""Who in Finance decided a price: their name, as Bishnoi One Finance sends it.

Finance approves prices in its own app, where its people aren't CRM users, so
approved_by_id stays empty for them and the name says who.

Revision ID: 0063
Revises: 0062
"""

from alembic import op
import sqlalchemy as sa

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("nbcm_product_prices", "nbcm_team_prices"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("approved_by_name", sa.String(120), nullable=True))


def downgrade() -> None:
    for table in ("nbcm_team_prices", "nbcm_product_prices"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("approved_by_name")
