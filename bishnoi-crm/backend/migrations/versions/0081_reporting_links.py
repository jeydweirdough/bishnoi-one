"""Reports to and assistant to (2026-11-03): the platform's links between people, kept here so a manager's reach follows
them. Two nullable columns on the people, added in place.

Revision ID: 0081
Revises: 0080
"""

import sqlalchemy as sa
from alembic import op

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("nbcm_users")}
    for name in ("reports_to_id", "assistant_of_id"):
        if name not in have:
            op.add_column("nbcm_users", sa.Column(name, sa.String(length=36), nullable=True))
            op.create_index(f"ix_nbcm_users_{name}", "nbcm_users", [name])


def downgrade() -> None:
    for name in ("reports_to_id", "assistant_of_id"):
        op.drop_index(f"ix_nbcm_users_{name}", table_name="nbcm_users")
    with op.batch_alter_table("nbcm_users") as batch:
        batch.drop_column("reports_to_id")
        batch.drop_column("assistant_of_id")
