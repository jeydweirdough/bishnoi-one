"""Whether a division's customers show to other divisions (look-alikes when
adding a customer, and fields that point at another customer). On by default,
as it was before.

Revision ID: 0050
Revises: 0049
"""

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_teams")}
    if "share_customers" not in have:
        with op.batch_alter_table("nbcm_teams") as batch:
            batch.add_column(sa.Column("share_customers", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table("nbcm_teams") as batch:
        batch.drop_column("share_customers")
