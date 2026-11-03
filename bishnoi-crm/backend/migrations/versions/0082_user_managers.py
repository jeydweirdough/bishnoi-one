"""Who sees a person (2026-11-04): a list of managers by email, from the platform's units' heads. One new table.

Revision ID: 0082
Revises: 0081
"""

import sqlalchemy as sa
from alembic import op

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_user_managers" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbcm_user_managers",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("manager_email", sa.String(254), primary_key=True),
    )
    op.create_index("ix_nbcm_user_managers_manager_email", "nbcm_user_managers", ["manager_email"])


def downgrade() -> None:
    op.drop_index("ix_nbcm_user_managers_manager_email", table_name="nbcm_user_managers")
    op.drop_table("nbcm_user_managers")
