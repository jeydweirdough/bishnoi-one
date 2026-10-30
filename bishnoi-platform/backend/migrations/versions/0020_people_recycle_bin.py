"""People's recycle bin (2026-10-30): a company administrator deletes a person to the recycle bin
(switched off, out of People, their sign-ins ended) and can restore them. Nothing is erased: what they
did keeps pointing at them. Two columns on memberships, added in place.

Revision ID: 0020
Revises: 0019
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbpl_identities")}
    if "deleted_at" not in have:
        op.add_column("nbpl_identities", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    if "deleted_by" not in have:
        op.add_column("nbpl_identities", sa.Column("deleted_by", sa.String(254), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("nbpl_identities") as batch:
        batch.drop_column("deleted_by")
        batch.drop_column("deleted_at")
