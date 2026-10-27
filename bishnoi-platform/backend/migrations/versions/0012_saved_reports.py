"""Saved reports: a report someone built from one of a module's reports, kept with their
choices only (decided 2026-10-26).

Revision ID: 0012
Revises: 0011
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nbpl_saved_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("nbpl_identities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("app_key", sa.String(40), nullable=False, index=True),
        sa.Column("base_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("shared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("nbpl_saved_reports")
