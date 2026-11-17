"""Company passes last 30 days, and each one the platform gives (asked for by an
application, or sent to it when the company changes) is recorded here.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "nbpl_company_passes" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "nbpl_company_passes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("nbpl_companies.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("company_slug", sa.String(40), nullable=False),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("nbpl_applications.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("how", sa.String(10), nullable=False),
        sa.Column("answer", sa.String(80), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("nbpl_company_passes")
