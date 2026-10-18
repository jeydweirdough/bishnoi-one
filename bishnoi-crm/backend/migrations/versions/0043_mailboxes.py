"""Each person's own connected mailbox, to send email from the CRM.

Revision ID: 0043
Revises: 0042
"""

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_mailboxes" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbcm_mailboxes",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("nbcm_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("address", sa.String(254), nullable=False),
        sa.Column("values", sa.JSON, nullable=False),
        sa.Column("secrets", sa.Text, nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(300), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("nbcm_mailboxes")
