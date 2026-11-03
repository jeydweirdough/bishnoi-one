"""A role in each app (2026-10-31): a person's role is kept on each app they may open (their grant), so the same
person can be a Salesperson in the CRM and Warehouse in Inventory. Everyone keeps today's role: it is copied onto
each of their apps. The person's own role stays, for an app given without one. One column, added in place.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "access_role_id" not in {c["name"] for c in sa.inspect(bind).get_columns("nbpl_identity_apps")}:
        op.add_column("nbpl_identity_apps", sa.Column("access_role_id", sa.String(length=36), nullable=True))
        op.create_index("ix_nbpl_identity_apps_access_role_id", "nbpl_identity_apps", ["access_role_id"])
    op.execute(
        "UPDATE nbpl_identity_apps SET access_role_id = (SELECT access_role_id FROM nbpl_identities WHERE nbpl_identities.id = nbpl_identity_apps.identity_id)"
        " WHERE access_role_id IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_nbpl_identity_apps_access_role_id", table_name="nbpl_identity_apps")
    with op.batch_alter_table("nbpl_identity_apps") as batch:
        batch.drop_column("access_role_id")
