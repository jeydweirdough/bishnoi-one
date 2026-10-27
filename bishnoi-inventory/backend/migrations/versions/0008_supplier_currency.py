"""A supplier's currency (decided 2026-10-27, with Zoho's vendors brought in): the
suppliers abroad (Hetero, Taj, Swiss Parenterals...) bill in USD. PHP unless said.

Revision ID: 0008
Revises: 0007
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nbin_suppliers") as batch:
        batch.add_column(sa.Column("currency", sa.String(3), nullable=False, server_default="PHP"))


def downgrade() -> None:
    with op.batch_alter_table("nbin_suppliers") as batch:
        batch.drop_column("currency")
