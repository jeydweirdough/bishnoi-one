"""Approved email templates, sent by reps with a personal note.

Revision ID: 0044
Revises: 0043
"""

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbcm_email_templates" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbcm_email_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("only_teams", sa.JSON, nullable=False),
        sa.Column("approved_on", sa.String(10), nullable=False),
        sa.Column("expires_on", sa.String(10), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("nbcm_email_templates")
