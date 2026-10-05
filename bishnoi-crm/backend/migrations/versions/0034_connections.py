"""Connections to outside services (Zoho Books first), set up by an administrator.

Revision ID: 0034
Revises: 0033
"""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_connections" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbcm_connections",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("values", sa.JSON, nullable=False),
        sa.Column("secrets", sa.Text, nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_ok", sa.Boolean, nullable=True),
        sa.Column("check_message", sa.String(300), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("nbcm_connections")
