"""Promos and bundles belong to divisions (teams): a B2C promo isn't seen or
quoted in B2B. Those already here get none, so nobody quotes them until an
administrator picks their divisions.

- nbcm_promos.team_ids, nbcm_bundles.team_ids: the divisions, as a list.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Like 0015: only if it isn't done yet, for a database whose recorded
    # revision fell behind its tables.
    inspector = sa.inspect(op.get_bind())
    for table in ("nbcm_promos", "nbcm_bundles"):
        if "team_ids" in {c["name"] for c in inspector.get_columns(table)}:
            continue
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("team_ids", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    for table in ("nbcm_promos", "nbcm_bundles"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("team_ids")
