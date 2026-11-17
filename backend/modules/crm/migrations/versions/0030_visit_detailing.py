"""The structured visit record (P6): what was detailed on a visit, in order,
with the key message and the doctor's reaction; and the next visit's objective.

Revision ID: 0030
Revises: 0029
"""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_visits")}
    with op.batch_alter_table("nbcm_visits") as batch:
        if "detailing" not in columns:
            batch.add_column(sa.Column("detailing", sa.JSON(), nullable=False, server_default="[]"))
        if "next_objective" not in columns:
            batch.add_column(sa.Column("next_objective", sa.String(300), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_visits") as batch:
        batch.drop_column("next_objective")
        batch.drop_column("detailing")
