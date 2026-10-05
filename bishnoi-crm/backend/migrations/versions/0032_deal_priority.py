"""A deal's priority: urgent, high, normal or low (or not said).

Revision ID: 0032
Revises: 0031
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_deals")}
    if "priority" not in columns:
        with op.batch_alter_table("nbcm_deals") as batch:
            batch.add_column(sa.Column("priority", sa.String(8), nullable=True))
            batch.create_index("ix_nbcm_deals_priority", ["priority"])


def downgrade() -> None:
    with op.batch_alter_table("nbcm_deals") as batch:
        batch.drop_index("ix_nbcm_deals_priority")
        batch.drop_column("priority")
